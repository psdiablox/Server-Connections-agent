"""Polymarket CLOB market-data websocket subscriber.

Subscribes to all token ids whose market has not yet ended. Persists:
  - book snapshots (deduped by hash)
  - book diffs (price_change events)
  - last trade prices (-> trades + price_snapshots.last)
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import orjson
import websockets

from .config import settings
from .db import pool

log = logging.getLogger("trace.clob")

# How long after market end we keep the subscription open (capture late settles).
SUBSCRIPTION_GRACE = timedelta(minutes=2)


async def _active_outcomes() -> list[tuple[str, int, int]]:
    """Returns [(token_id, market_id, outcome_id), …] for markets currently in scope."""
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
    raw = orjson.dumps([bids, asks])
    return hashlib.sha256(raw).hexdigest()


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


async def _on_book(token_to_outcome: dict, msg: dict) -> None:
    asset = msg.get("asset_id") or msg.get("market")
    info = token_to_outcome.get(asset)
    if not info:
        return
    market_id, outcome_id = info
    bids = _normalize_levels(msg.get("bids"))
    asks = _normalize_levels(msg.get("asks"))
    h = msg.get("hash") or _hash_book(bids, asks)
    ts = _parse_ts(msg.get("timestamp"))

    async with pool().acquire() as conn:
        prev = await conn.fetchval(
            """
            SELECT hash FROM polymarket.book_snapshots
            WHERE market_id=$1 AND outcome_id=$2
            ORDER BY ts DESC LIMIT 1
            """,
            market_id, outcome_id,
        )
        if prev == h:
            return  # dedup: identical book — skip
        await conn.execute(
            """
            INSERT INTO polymarket.book_snapshots (market_id, outcome_id, ts, bids, asks, hash)
            VALUES ($1,$2,$3,$4,$5,$6)
            """,
            market_id, outcome_id, ts, bids, asks, h,
        )
        # Also derive a price_snapshot row.
        best_bid = max((p for p, _ in bids), default=None)
        best_ask = min((p for p, _ in asks), default=None)
        mid = (best_bid + best_ask) / 2 if best_bid is not None and best_ask is not None else None
        await conn.execute(
            """
            INSERT INTO polymarket.price_snapshots (market_id, outcome_id, ts, best_bid, best_ask, mid, last)
            VALUES ($1,$2,$3,$4,$5,$6,NULL)
            """,
            market_id, outcome_id, ts, best_bid, best_ask, mid,
        )


async def _on_price_change(token_to_outcome: dict, msg: dict) -> None:
    asset = msg.get("asset_id")
    info = token_to_outcome.get(asset)
    if not info:
        return
    market_id, outcome_id = info
    ts = _parse_ts(msg.get("timestamp"))
    # Polymarket sends one or many changes; normalize to a list.
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
                """
                INSERT INTO polymarket.book_events (market_id, outcome_id, ts, side, price, size)
                VALUES ($1,$2,$3,$4,$5,$6)
                """,
                market_id, outcome_id, ts, side, price, size,
            )


async def _on_last_trade(token_to_outcome: dict, msg: dict) -> None:
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
    external_id = str(msg.get("trade_id") or msg.get("id") or "")
    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO polymarket.trades
                (market_id, outcome_id, ts, price, size, side, taker_address, maker_address, tx_hash, external_id)
            VALUES ($1,$2,$3,$4,$5,$6,NULL,NULL,NULL,$7)
            ON CONFLICT (market_id, outcome_id, ts, COALESCE(external_id,'')) DO NOTHING
            """,
            market_id, outcome_id, ts, price, size, side, external_id or None,
        )
        await conn.execute(
            """
            INSERT INTO polymarket.price_snapshots (market_id, outcome_id, ts, best_bid, best_ask, mid, last)
            VALUES ($1,$2,$3,NULL,NULL,NULL,$4)
            """,
            market_id, outcome_id, ts, price,
        )


async def _session(token_to_outcome: dict, token_ids: list[str], stop: asyncio.Event) -> None:
    """Run one CLOB websocket connection until stop is set or peer closes."""
    log.info("clob ws connecting (%d tokens)", len(token_ids))
    async with websockets.connect(
        settings.polymarket_clob_ws,
        ping_interval=20,
        ping_timeout=20,
        max_size=8 * 1024 * 1024,
    ) as ws:
        await ws.send(orjson.dumps({"type": "market", "assets_ids": token_ids}).decode())
        while not stop.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
            except asyncio.TimeoutError:
                continue
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
                        await _on_book(token_to_outcome, msg)
                    elif evt == "price_change":
                        await _on_price_change(token_to_outcome, msg)
                    elif evt == "last_trade_price":
                        await _on_last_trade(token_to_outcome, msg)
                except Exception:
                    log.exception("clob handler error (event=%s)", evt)


async def clob_loop(market_signal: asyncio.Event) -> None:
    """Reconnect on signal (new markets) or on ws drop."""
    while True:
        outcomes = await _active_outcomes()
        if not outcomes:
            log.info("no active polymarket outcomes; sleeping")
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(market_signal.wait(), timeout=30)
            market_signal.clear()
            continue

        token_to_outcome = {tok: (mid, oid) for tok, mid, oid in outcomes}
        token_ids = list(token_to_outcome.keys())
        stop = asyncio.Event()

        async def watch_signal():
            await market_signal.wait()
            market_signal.clear()
            stop.set()

        watcher = asyncio.create_task(watch_signal())
        try:
            await _session(token_to_outcome, token_ids, stop)
        except Exception:
            log.exception("clob session crashed; reconnecting in 5s")
            await asyncio.sleep(5)
        finally:
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher
