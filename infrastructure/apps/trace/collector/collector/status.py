"""Periodic aggregator: rolls trades into core.markets summary fields and
flips status (upcoming -> live -> ended) based on current time."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from .config import settings
from .db import pool

log = logging.getLogger("trace.status")


async def _update_statuses() -> None:
    now = datetime.now(tz=timezone.utc)
    async with pool().acquire() as conn:
        await conn.execute(
            """
            UPDATE core.markets
            SET status = CASE
                WHEN ends_at <= $1 THEN 'ended'
                WHEN starts_at <= $1 AND $1 < ends_at THEN 'live'
                ELSE 'upcoming'
            END,
            updated_at = now()
            WHERE network_id = (SELECT id FROM core.networks WHERE slug='polymarket')
              AND (
                (status = 'upcoming' AND starts_at <= $1) OR
                (status = 'live' AND ends_at <= $1)
              )
            """,
            now,
        )


async def _set_strike_for_started_markets() -> None:
    """For any Polymarket BTC market that has just started (status flipped to
    live or ended) and has no strike yet, take the BTC spot price closest to
    starts_at and store it as the strike — these markets resolve YES if BTC
    closed above this opening price, NO otherwise."""
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT m.id, m.starts_at, m.coin_id
            FROM core.markets m
            JOIN core.networks n ON n.id = m.network_id
            WHERE n.slug='polymarket'
              AND m.status IN ('live','ended')
              AND m.strike IS NULL
              AND m.coin_id IS NOT NULL
            LIMIT 50
            """
        )
        for r in rows:
            price = await conn.fetchval(
                """
                SELECT price FROM polymarket.coin_prices
                WHERE coin_id=$1 AND ts <= $2
                ORDER BY ts DESC LIMIT 1
                """,
                r["coin_id"], r["starts_at"],
            )
            if price is not None:
                await conn.execute(
                    "UPDATE core.markets SET strike=$1, updated_at=now() WHERE id=$2",
                    float(price), r["id"],
                )


async def _update_aggregates() -> None:
    """For each market touched recently, recompute volume / trade-count /
    largest-trade / avg-trade / last-yes / last-no / close-btc."""
    async with pool().acquire() as conn:
        market_ids = await conn.fetch(
            """
            SELECT DISTINCT m.id, m.starts_at, m.ends_at, m.coin_id
            FROM core.markets m
            JOIN core.networks n ON n.id = m.network_id
            WHERE n.slug='polymarket'
              AND m.status IN ('live','ended')
              AND m.updated_at > now() - INTERVAL '1 day'
            """
        )
        for row in market_ids:
            mid = row["id"]
            window_start = row["starts_at"]
            window_end = row["ends_at"]
            coin_id = row["coin_id"]

            stats = await conn.fetchrow(
                """
                SELECT
                  COALESCE(SUM(price * size), 0) AS volume,
                  COUNT(*) AS trade_count,
                  MAX(price * size) AS largest,
                  AVG(price * size) AS avg_size,
                  COUNT(DISTINCT taker_address) FILTER (WHERE taker_address IS NOT NULL) AS traders
                FROM polymarket.trades
                WHERE market_id = $1 AND ts >= $2 AND ts <= $3
                """,
                mid, window_start, window_end,
            )
            yes_outcome = await conn.fetchval(
                "SELECT id FROM core.market_outcomes WHERE market_id=$1 AND label='YES'", mid
            )
            no_outcome = await conn.fetchval(
                "SELECT id FROM core.market_outcomes WHERE market_id=$1 AND label='NO'", mid
            )
            last_yes = await conn.fetchval(
                """SELECT COALESCE(mid, last) FROM polymarket.price_snapshots
                   WHERE market_id=$1 AND outcome_id=$2
                   ORDER BY ts DESC LIMIT 1""",
                mid, yes_outcome,
            ) if yes_outcome else None
            last_no = await conn.fetchval(
                """SELECT COALESCE(mid, last) FROM polymarket.price_snapshots
                   WHERE market_id=$1 AND outcome_id=$2
                   ORDER BY ts DESC LIMIT 1""",
                mid, no_outcome,
            ) if no_outcome else None
            # BTC spot at the moment closest to (and not beyond) window_end.
            close_btc = await conn.fetchval(
                """SELECT price FROM polymarket.coin_prices
                   WHERE coin_id=$1 AND ts <= $2
                   ORDER BY ts DESC LIMIT 1""",
                coin_id, window_end,
            ) if coin_id else None

            await conn.execute(
                """
                UPDATE core.markets
                SET total_volume   = $2,
                    traders        = $3,
                    last_yes       = $4,
                    last_no        = $5,
                    trade_count    = $6,
                    largest_trade  = $7,
                    avg_trade      = $8,
                    close_btc      = $9
                WHERE id = $1
                """,
                mid,
                float(stats["volume"]) if stats["volume"] is not None else 0.0,
                int(stats["traders"]) if stats["traders"] is not None else 0,
                float(last_yes) if last_yes is not None else None,
                float(last_no) if last_no is not None else None,
                int(stats["trade_count"]) if stats["trade_count"] is not None else 0,
                float(stats["largest"]) if stats["largest"] is not None else None,
                float(stats["avg_size"]) if stats["avg_size"] is not None else None,
                float(close_btc) if close_btc is not None else None,
            )


async def status_loop() -> None:
    while True:
        try:
            await _update_statuses()
            await _set_strike_for_started_markets()
            await _update_aggregates()
        except Exception:
            log.exception("status loop error")
        await asyncio.sleep(settings.status_interval_seconds)
