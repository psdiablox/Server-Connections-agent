"""Polymarket CLOB market-data websocket subscriber.

Subscribes to all token ids whose market has not yet ended. Persists:
  - book snapshots (deduped by hash)
  - book diffs (price_change events)
  - last trade prices (-> trades + price_snapshots.last)

Reliability rules:
  - Each session is bounded to SESSION_MAX seconds (5 min). Then we drop and
    reconnect with the freshest list of active tokens — this is how new markets
    are picked up without a per-discovery reconnect storm.
  - If no message arrives for IDLE_MAX seconds, the session is killed. Empirically
    Polymarket sometimes leaves the connection alive but stops streaming.
  - Reconnect backoff on errors capped at 30 s.
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import orjson
import websockets

from .config import settings
from .db import pool
from .health import Heartbeat, emit as emit_health

SOURCE = "polymarket-clob"

# Shared state used by the 1 Hz price emitter. Rebuilt at session start; written
# by event handlers; read by hz_emitter().
#   outcome_id -> {market_id, best_bid, best_ask, mid, last, last_event_ts}
_latest_state: dict[int, dict] = {}

log = logging.getLogger("trace.clob")

SUBSCRIPTION_GRACE = timedelta(minutes=2)
SESSION_MAX = 300       # cap a single ws session at 5 min, then refresh
IDLE_MAX = 45           # if no message in 45s, force reconnect
PING_INTERVAL = 20


async def _active_outcomes() -> list[tuple[str, int, int]]:
    cutoff = datetime.now(tz=timezone.utc) - SUBSCRIPTION_GRACE
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT mo.external_token_id, mo.market_id, mo.id
            FROM core.market_outcomes mo
            JOIN core.markets m ON m.id = mo.market_id
            JOIN core.networks n ON n.id = m.network_id
            WHERE n.slug='polymarket'
              AND mo.external_token_id IS NOT NULL
              AND m.ends_at > $1
            """,
            cutoff,
        )
    return [(r["external_token_id"], r["market_id"], r["id"]) for r in rows]


def _hash_book(bids: list, asks: list) -> str:
    return hashlib.sha256(orjson.dumps([bids, asks])).hexdigest()


def _normalize_levels(levels: list) -> list[list[float]]:
    out: list[list[float]] = []
    for lvl in levels or []:
        try:
            if isinstance(lvl, dict):
                p = float(lvl["price"])
                s = float(lvl["size"])
            else:
                p, s = float(lvl[0]), float(lvl[1])
            out.append([p, s])
        except (KeyError, ValueError, TypeError, IndexError):
            continue
    return out


def _parse_ts(raw) -> datetime:
    if raw is None:
        return datetime.now(tz=timezone.utc)
    try:
        ms = int(raw)
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(tz=timezone.utc)


async def _on_book(token_to_outcome: dict, msg: dict, stats: dict) -> None:
    asset = msg.get("asset_id") or msg.get("market")
    info = token_to_outcome.get(asset)
    if not info:
        return
    market_id, outcome_id = info
    bids = _normalize_levels(msg.get("bids"))
    asks = _normalize_levels(msg.get("asks"))
    h = msg.get("hash") or _hash_book(bids, asks)
    ts = _parse_ts(msg.get("timestamp"))
    best_bid = max((p for p, _ in bids), default=None)
    best_ask = min((p for p, _ in asks), default=None)
    mid = (best_bid + best_ask) / 2 if best_bid is not None and best_ask is not None else None

    # Update shared state so the 1 Hz emitter has fresh values to write.
    prev = _latest_state.get(outcome_id, {})
    _latest_state[outcome_id] = {
        "market_id": market_id,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid": mid,
        "last": prev.get("last"),
        "last_event_ts": ts,
    }

    # Record every book — no dedup.
    async with pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO polymarket.book_snapshots
               (market_id, outcome_id, ts, bids, asks, hash)
               VALUES ($1,$2,$3,$4,$5,$6)""",
            market_id, outcome_id, ts, bids, asks, h,
        )
        stats["book"] += 1


async def _on_price_change(token_to_outcome: dict, msg: dict, stats: dict) -> None:
    asset = msg.get("asset_id")
    info = token_to_outcome.get(asset)
    if not info:
        return
    market_id, outcome_id = info
    ts = _parse_ts(msg.get("timestamp"))
    changes = msg.get("changes") or [msg]
    async with pool().acquire() as conn:
        for ch in changes:
            try:
                price = float(ch["price"])
                size = float(ch["size"])
                side_raw = (ch.get("side") or "").upper()
            except (KeyError, ValueError, TypeError):
                continue
            side = "bid" if side_raw == "BUY" else "ask" if side_raw == "SELL" else side_raw.lower()
            await conn.execute(
                """INSERT INTO polymarket.book_events
                   (market_id, outcome_id, ts, side, price, size)
                   VALUES ($1,$2,$3,$4,$5,$6)""",
                market_id, outcome_id, ts, side, price, size,
            )
            stats["book_event"] += 1


async def _on_last_trade(token_to_outcome: dict, msg: dict, stats: dict) -> None:
    asset = msg.get("asset_id")
    info = token_to_outcome.get(asset)
    if not info:
        return
    market_id, outcome_id = info
    ts = _parse_ts(msg.get("timestamp"))
    try:
        price = float(msg["price"])
        size = float(msg["size"])
    except (KeyError, ValueError, TypeError):
        return
    side = (msg.get("side") or "").upper()
    if side not in ("BUY", "SELL"):
        side = "BUY"
    external_id = (
        msg.get("transaction_hash")
        or msg.get("trade_id")
        or msg.get("id")
        or f"{ts.isoformat()}-{price}-{size}"
    )

    # Update shared state — last trade price for the 1 Hz emitter.
    state = _latest_state.setdefault(outcome_id, {"market_id": market_id})
    state["last"] = price
    state["last_event_ts"] = ts

    async with pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO polymarket.trades
               (market_id, outcome_id, ts, price, size, side, taker_address, maker_address, tx_hash, external_id)
               VALUES ($1,$2,$3,$4,$5,$6,NULL,NULL,$7,$8)
               ON CONFLICT (market_id, outcome_id, ts, COALESCE(external_id,'')) DO NOTHING""",
            market_id, outcome_id, ts, price, size, side,
            msg.get("transaction_hash"), str(external_id),
        )
        stats["trade"] += 1


async def _hz_price_emitter(stop: asyncio.Event) -> None:
    """Writes one price_snapshots row per active outcome every second using
    whatever values are most recently in _latest_state. Guarantees a regular
    1 Hz time grid for charting even when book/trade events are silent."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=1.0)
            return
        except asyncio.TimeoutError:
            pass
        if not _latest_state:
            continue
        now = datetime.now(tz=timezone.utc)
        rows = [
            (
                s.get("market_id"),
                oid,
                now,
                s.get("best_bid"),
                s.get("best_ask"),
                s.get("mid"),
                s.get("last"),
            )
            for oid, s in list(_latest_state.items())
            if s.get("market_id") is not None
        ]
        if not rows:
            continue
        try:
            async with pool().acquire() as conn:
                await conn.executemany(
                    """INSERT INTO polymarket.price_snapshots
                       (market_id, outcome_id, ts, best_bid, best_ask, mid, last)
                       VALUES ($1,$2,$3,$4,$5,$6,$7)
                       ON CONFLICT DO NOTHING""",
                    rows,
                )
        except Exception:
            log.exception("hz emitter insert error")


async def _session(token_to_outcome: dict, token_ids: list[str]) -> str:
    """Run one ws session. Returns reason for exit: 'idle' | 'deadline' | 'closed' | 'error'."""
    log.info("clob ws connecting (%d tokens)", len(token_ids))
    stats = {"book": 0, "book_event": 0, "trade": 0}
    started = time.time()
    deadline = started + SESSION_MAX
    hb = Heartbeat(SOURCE)
    # Reset shared state to only the outcomes this session is subscribed to.
    _latest_state.clear()
    hz_stop = asyncio.Event()
    hz_task = asyncio.create_task(_hz_price_emitter(hz_stop), name="hz-price")
    try:
        async with websockets.connect(
            settings.polymarket_clob_ws,
            ping_interval=PING_INTERVAL,
            ping_timeout=PING_INTERVAL,
            max_size=8 * 1024 * 1024,
            close_timeout=5,
        ) as ws:
            await ws.send(orjson.dumps({"type": "market", "assets_ids": token_ids}).decode())
            hb.start()
            last_msg = time.time()
            while True:
                now = time.time()
                if now >= deadline:
                    log.info("clob session ok session_max | %s", stats)
                    await hb.stop(None)
                    return "deadline"
                remaining = max(1.0, min(deadline - now, IDLE_MAX - (now - last_msg)))
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    if time.time() - last_msg > IDLE_MAX:
                        log.warning("clob idle %ds, reconnecting | %s", IDLE_MAX, stats)
                        await hb.stop(f"polymarket ws idle {IDLE_MAX}s — no messages received")
                        return "idle"
                    continue
                last_msg = time.time()
                try:
                    payload = orjson.loads(raw)
                except orjson.JSONDecodeError:
                    continue
                msgs = payload if isinstance(payload, list) else [payload]
                for msg in msgs:
                    if not isinstance(msg, dict):
                        continue
                    evt = msg.get("event_type")
                    try:
                        if evt == "book":
                            await _on_book(token_to_outcome, msg, stats)
                        elif evt == "price_change":
                            await _on_price_change(token_to_outcome, msg, stats)
                        elif evt == "last_trade_price":
                            await _on_last_trade(token_to_outcome, msg, stats)
                    except Exception:
                        log.exception("clob handler error (event=%s)", evt)
    except Exception as e:
        log.exception("clob session crashed | %s", stats)
        await hb.stop(f"polymarket ws crashed: {type(e).__name__}: {e}")
        return "error"
    finally:
        hz_stop.set()
        try:
            await asyncio.wait_for(hz_task, timeout=2)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            hz_task.cancel()
    await hb.stop("polymarket ws closed by peer")
    log.info("clob session closed | %s", stats)
    return "closed"


async def clob_loop(market_signal: asyncio.Event) -> None:
    """Refresh subscription set once per session bound. New markets discovered
    mid-session are picked up on the next refresh (≤5 min). market_signal is
    no longer used for hot reconnects — it caused storms."""
    log.info("clob loop starting")
    backoff = 1.0
    while True:
        outcomes = await _active_outcomes()
        if not outcomes:
            log.info("no active polymarket outcomes; sleeping 30s")
            await asyncio.sleep(30)
            continue

        token_to_outcome = {tok: (mid, oid) for tok, mid, oid in outcomes}
        token_ids = list(token_to_outcome.keys())

        reason = await _session(token_to_outcome, token_ids)
        if reason == "error":
            await asyncio.sleep(min(30.0, backoff))
            backoff = min(30.0, backoff * 2)
        else:
            backoff = 1.0
        # Drain any pending market_signal; we re-read outcomes on next iter.
        if market_signal.is_set():
            market_signal.clear()
