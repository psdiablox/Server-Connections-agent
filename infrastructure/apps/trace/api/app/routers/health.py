"""Operational health endpoints — auth-free so Uptime Kuma (or any external
monitor) can poll them. The router intentionally does NOT depend on
require_user; it leaks only an "ok / not ok + reason" signal, no data."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Response

from ..db import pool

router = APIRouter(prefix="/api/health", tags=["health"])

# A live market should produce trades or book snapshots constantly. If the
# most recent insert is older than this while a market is live, declare the
# collector silent.
SILENCE_BUDGET_SECONDS = 90


@router.get("/collector")
async def collector_health(response: Response) -> dict:
    """Returns 200 when:
       - there is no live polymarket market right now (idle is normal); OR
       - there is a live market AND we've inserted at least one row in the
         last SILENCE_BUDGET_SECONDS seconds.
       Returns 503 otherwise, with `reason` telling the operator why.
    """
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(seconds=SILENCE_BUDGET_SECONDS)
    async with pool().acquire() as conn:
        last_trade = await conn.fetchval("SELECT max(ts) FROM polymarket.trades")
        last_book = await conn.fetchval("SELECT max(ts) FROM polymarket.book_snapshots")
        last_coin = await conn.fetchval("SELECT max(ts) FROM polymarket.coin_prices")
        recent_trades = await conn.fetchval(
            "SELECT count(*) FROM polymarket.trades WHERE ts > $1", cutoff
        )
        # Per-live-market freshness: any live polymarket market that has had
        # NO trade and NO book event in the last SILENCE_BUDGET_SECONDS is
        # the case that snuck past us before — Polymarket silently dropped
        # this market's subscription while keeping the WS connection up.
        stale_rows = await conn.fetch(
            """
            SELECT m.id,
                   GREATEST(
                     COALESCE((SELECT max(ts) FROM polymarket.trades         WHERE market_id = m.id), 'epoch'::timestamptz),
                     COALESCE((SELECT max(ts) FROM polymarket.book_snapshots WHERE market_id = m.id), 'epoch'::timestamptz)
                   ) AS last_event,
                   m.starts_at
            FROM core.markets m
            JOIN core.networks n ON n.id = m.network_id
            WHERE n.slug='polymarket' AND m.status='live'
            """
        )
    live_count = len(stale_rows)
    stale_markets: list[dict] = []
    for r in stale_rows:
        last_event = r["last_event"]
        # Only flag if the market has been live long enough to expect data.
        # New live markets get a 30 s grace from starts_at to first event.
        grace_until = r["starts_at"] + timedelta(seconds=30)
        if now < grace_until:
            continue
        if last_event is None or last_event.year < 2000 or (now - last_event).total_seconds() > SILENCE_BUDGET_SECONDS:
            stale_markets.append({
                "market_id": r["id"],
                "last_event_at": last_event.isoformat() if last_event and last_event.year > 2000 else None,
                "silent_seconds": (now - last_event).total_seconds() if last_event and last_event.year > 2000 else None,
            })

    body: dict = {
        "ok": True,
        "live_markets": live_count,
        "last_trade_at": last_trade.isoformat() if last_trade else None,
        "last_book_at": last_book.isoformat() if last_book else None,
        "last_coin_price_at": last_coin.isoformat() if last_coin else None,
        "recent_trades_90s": int(recent_trades or 0),
        "stale_markets": stale_markets,
        "now": now.isoformat(),
    }

    if last_coin is None or last_coin < cutoff:
        body["ok"] = False
        body["reason"] = "binance ws silent — no btc price snapshot in 90s"
        response.status_code = 503
        return body

    if stale_markets:
        body["ok"] = False
        body["reason"] = (
            f"{len(stale_markets)} live market(s) silent for >{SILENCE_BUDGET_SECONDS}s — "
            "Polymarket WS likely dropped these subscriptions"
        )
        response.status_code = 503
        return body

    if live_count > 0:
        last_pm = max((t for t in (last_trade, last_book) if t is not None), default=None)
        if last_pm is None or last_pm < cutoff:
            body["ok"] = False
            body["reason"] = (
                f"live polymarket market but no trade/book insert in "
                f"{SILENCE_BUDGET_SECONDS}s — WS or DB issue"
            )
            response.status_code = 503
            return body

    return body
