from __future__ import annotations
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
import websockets
import websockets.exceptions

import config
import db
from state import CollectorState, Market

log = logging.getLogger(__name__)


# ── Market discovery ──────────────────────────────────────────────────────────

def _current_window_slugs() -> list[str]:
    """Return slugs for the current + next two 5-min windows."""
    base = int(time.time() / 300) * 300
    return [f"btc-updown-5m-{base + i * 300}" for i in range(2)]


def _parse_market_row(raw: dict) -> Optional[tuple]:
    """Extract fields from a Gamma API market object. Returns None if incomplete."""
    condition_id     = raw.get("conditionId") or raw.get("condition_id")
    question         = raw.get("question", "")
    clob_token_ids   = raw.get("clobTokenIds")
    outcomes_raw     = raw.get("outcomes")
    start_date       = raw.get("startDate") or raw.get("start_date")
    end_date         = raw.get("endDate")   or raw.get("end_date")

    if not all([condition_id, clob_token_ids, outcomes_raw, start_date, end_date]):
        return None

    try:
        token_ids = json.loads(clob_token_ids) if isinstance(clob_token_ids, str) else clob_token_ids
        outcomes  = json.loads(outcomes_raw)   if isinstance(outcomes_raw, str)  else outcomes_raw
        start_ts  = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end_ts    = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    except Exception:
        return None

    if len(token_ids) < 2 or len(outcomes) < 2:
        return None

    return condition_id, token_ids[0], token_ids[1], outcomes[0], outcomes[1], question, start_ts, end_ts


async def discover_markets(state: CollectorState) -> None:
    """Fetch current + upcoming BTC 5-min windows by deterministic slug."""
    known = state.known_conditions()
    new_count = 0

    async with httpx.AsyncClient(timeout=10) as client:
        for slug in _current_window_slugs():
            try:
                resp = await client.get(f"{config.GAMMA_API}/events", params={"slug": slug})
                resp.raise_for_status()
                events = resp.json()
            except Exception as exc:
                log.debug("event fetch failed for %s: %s", slug, exc)
                continue

            for event in events:
                for raw in event.get("markets", []):
                    parsed = _parse_market_row(raw)
                    if not parsed:
                        continue
                    condition_id, yes_tok, no_tok, yes_out, no_out, question, start_ts, end_ts = parsed
                    if condition_id in known:
                        continue

                    market_id = await db.upsert_market(
                        condition_id, yes_tok, no_tok,
                        yes_out, no_out, question, start_ts, end_ts,
                    )
                    m = Market(market_id, condition_id, yes_tok, no_tok, yes_out, no_out, question)
                    state.add_market(m)
                    known.add(condition_id)
                    new_count += 1
                    log.info("new market [db_id=%d] %s", market_id, question[:70])

    if new_count:
        log.info("discovery: %d new market(s) added", new_count)


async def discover_loop(state: CollectorState) -> None:
    while True:
        await discover_markets(state)
        await asyncio.sleep(config.DISCOVERY_SEC)


# ── WebSocket event handlers ──────────────────────────────────────────────────

async def _handle_book(msg: dict, state: CollectorState) -> None:
    """Full order book snapshot — fired on subscribe and after each trade."""
    token_id = msg.get("asset_id")
    if not token_id:
        return
    market = state.by_token(token_id)
    if not market:
        return

    book  = state.book(token_id)
    buys  = msg.get("buys",  [])
    sells = msg.get("sells", [])
    book.apply_snapshot(buys, sells)

    bids, asks = book.sorted_snapshot()
    await db.insert_book_checkpoint(
        datetime.now(timezone.utc), market.db_id, token_id, bids, asks
    )
    log.debug("checkpoint: token=%s… bids=%d asks=%d", token_id[:12], len(bids), len(asks))


async def _handle_price_change(msg: dict, state: CollectorState) -> None:
    """Order book delta — fired for every new or cancelled order.
    size='0' means the price level was removed from the book."""
    ts = datetime.now(timezone.utc)
    # Field is 'price_changes' per Polymarket docs
    changes = msg.get("price_changes") or msg.get("changes", [])
    delta_rows: list[tuple] = []

    for ch in changes:
        token_id = ch.get("asset_id")
        if not token_id:
            continue
        market = state.by_token(token_id)
        if not market:
            continue

        side     = ch.get("side", "")
        price    = ch.get("price", "0")
        size     = ch.get("size",  "0")
        best_bid = ch.get("best_bid")
        best_ask = ch.get("best_ask")

        state.book(token_id).apply_delta(side, price, size, best_bid, best_ask)

        try:
            delta_rows.append((
                ts, market.db_id, token_id, side,
                float(price), float(size),   # size=0.0 means level removed
            ))
        except (ValueError, TypeError):
            continue

    if delta_rows:
        await db.insert_book_deltas(delta_rows)
        removals = sum(1 for r in delta_rows if r[5] == 0.0)
        log.debug(
            "book_deltas: %d saved (%d removals, size=0)",
            len(delta_rows), removals,
        )


async def _handle_trade(msg: dict, state: CollectorState) -> None:
    """Trade execution — fired for every fill."""
    token_id = msg.get("asset_id")
    if not token_id:
        return
    market = state.by_token(token_id)
    if not market:
        return

    outcome = market.outcome_for(token_id)
    try:
        ts = datetime.fromtimestamp(int(msg["timestamp"]), tz=timezone.utc)
    except Exception:
        ts = datetime.now(timezone.utc)

    price = msg.get("price", "0")
    size  = msg.get("size",  "0")
    side  = msg.get("side",  "BUY")

    await db.insert_trade(ts, market.db_id, token_id, outcome, price, size, side)
    log.info("trade: %s %s @ %s  size=%s", outcome, side, price, size)


async def _handle_market_resolved(msg: dict, state: CollectorState) -> None:
    condition_id = msg.get("condition_id") or msg.get("conditionId")
    outcome      = msg.get("outcome", "").upper()
    if condition_id and outcome in ("YES", "NO"):
        await db.mark_resolved(condition_id, outcome)
        log.info("market resolved: %s → %s", condition_id[:16], outcome)


_HANDLERS = {
    "book":             _handle_book,
    "price_change":     _handle_price_change,
    "last_trade_price": _handle_trade,
    "market_resolved":  _handle_market_resolved,
}


# ── WebSocket loop ────────────────────────────────────────────────────────────

async def ws_loop(state: CollectorState) -> None:
    subscribed: set[str] = set()

    while True:
        try:
            async with websockets.connect(
                config.CLOB_WS,
                ping_interval=None,  # manual PING
                open_timeout=15,
            ) as ws:
                log.info("websocket connected")
                subscribed.clear()

                # Subscribe to whatever markets are already known
                await _subscribe_new(ws, state, subscribed)

                ping_task = asyncio.create_task(
                    _ping_loop(ws, state, subscribed), name="ws-ping"
                )
                try:
                    async for raw in ws:
                        try:
                            payload = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        # WebSocket may send a single dict or a list of dicts
                        msgs = payload if isinstance(payload, list) else [payload]
                        for msg in msgs:
                            if not isinstance(msg, dict):
                                continue
                            event_type = msg.get("event_type") or msg.get("type", "")
                            if event_type in ("PONG", "pong"):
                                continue
                            handler = _HANDLERS.get(event_type)
                            if handler:
                                await handler(msg, state)
                            else:
                                log.debug("unhandled event: %s", event_type)
                finally:
                    ping_task.cancel()

        except (websockets.exceptions.ConnectionClosed, OSError, asyncio.TimeoutError) as exc:
            log.warning("websocket disconnected: %s — reconnecting in 5s", exc)
            await asyncio.sleep(5)
        except Exception as exc:
            log.error("websocket error: %s — reconnecting in 10s", exc, exc_info=True)
            await asyncio.sleep(10)


async def _subscribe_new(ws, state: CollectorState, subscribed: set[str]) -> None:
    new_tokens = [t for t in state.all_token_ids() if t not in subscribed]
    if not new_tokens:
        return
    await ws.send(json.dumps({
        "assets_ids": new_tokens,
        "type": "Market",
        "custom_feature_enabled": True,   # enables market_resolved events
    }))
    subscribed.update(new_tokens)
    log.info("subscribed to %d token(s)", len(new_tokens))


async def _ping_loop(ws, state: CollectorState, subscribed: set[str]) -> None:
    while True:
        await asyncio.sleep(10)
        try:
            await ws.send(json.dumps({"type": "PING"}))
            await _subscribe_new(ws, state, subscribed)  # picks up any new markets
        except Exception:
            break  # parent ws_loop will detect the disconnect


# ── Price REST poller ─────────────────────────────────────────────────────────

async def price_poll_loop(state: CollectorState) -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        while True:
            ts = datetime.now(timezone.utc)
            for market in state.all_markets():
                token_id = market.yes_token_id
                book     = state.book(token_id)
                mid: Optional[float] = None

                try:
                    resp = await client.get(
                        f"{config.CLOB_API}/midpoint",
                        params={"token_id": token_id},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    # API returns {"mid": "0.523"} — log once to confirm format
                    raw_mid = data.get("mid") or data.get("price") or data.get("midpoint")
                    mid = float(raw_mid) if raw_mid else None
                except Exception as exc:
                    log.debug("midpoint fetch failed for %s…: %s", token_id[:12], exc)

                await db.insert_price_snapshot(
                    ts, market.db_id, mid, book.best_bid, book.best_ask
                )

            await asyncio.sleep(config.PRICE_POLL_SEC)
