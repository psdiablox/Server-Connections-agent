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


async def _update_aggregates() -> None:
    """For each market touched in the last status interval window, recompute
    total_volume / traders / last_yes / last_no."""
    async with pool().acquire() as conn:
        market_ids = await conn.fetch(
            """
            SELECT DISTINCT m.id
            FROM core.markets m
            JOIN core.networks n ON n.id = m.network_id
            WHERE n.slug='polymarket'
              AND (m.status IN ('live','ended'))
              AND m.updated_at > now() - INTERVAL '1 day'
            """
        )
        for row in market_ids:
            mid = row["id"]
            stats = await conn.fetchrow(
                """
                SELECT
                  COALESCE(SUM(price * size), 0) AS volume,
                  COUNT(DISTINCT taker_address) FILTER (WHERE taker_address IS NOT NULL) AS traders
                FROM polymarket.trades WHERE market_id = $1
                """,
                mid,
            )
            yes_outcome = await conn.fetchval(
                "SELECT id FROM core.market_outcomes WHERE market_id=$1 AND label='YES'", mid
            )
            no_outcome = await conn.fetchval(
                "SELECT id FROM core.market_outcomes WHERE market_id=$1 AND label='NO'", mid
            )
            last_yes = await conn.fetchval(
                """
                SELECT COALESCE(mid, last) FROM polymarket.price_snapshots
                WHERE market_id=$1 AND outcome_id=$2
                ORDER BY ts DESC LIMIT 1
                """,
                mid, yes_outcome,
            ) if yes_outcome else None
            last_no = await conn.fetchval(
                """
                SELECT COALESCE(mid, last) FROM polymarket.price_snapshots
                WHERE market_id=$1 AND outcome_id=$2
                ORDER BY ts DESC LIMIT 1
                """,
                mid, no_outcome,
            ) if no_outcome else None
            await conn.execute(
                """
                UPDATE core.markets
                SET total_volume = $2,
                    traders = $3,
                    last_yes = $4,
                    last_no = $5
                WHERE id = $1
                """,
                mid,
                float(stats["volume"]) if stats["volume"] is not None else 0.0,
                int(stats["traders"]) if stats["traders"] is not None else 0,
                float(last_yes) if last_yes is not None else None,
                float(last_no) if last_no is not None else None,
            )


async def status_loop() -> None:
    while True:
        try:
            await _update_statuses()
            await _update_aggregates()
        except Exception:
            log.exception("status loop error")
        await asyncio.sleep(settings.status_interval_seconds)
