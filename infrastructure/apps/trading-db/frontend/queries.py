from __future__ import annotations
import json
from datetime import datetime
from typing import Optional
import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def init(db_url: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        db_url, min_size=2, max_size=5, init=_register_codecs
    )


async def _register_codecs(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


def _fmt(rows: list[asyncpg.Record]) -> list[dict]:
    result = []
    for row in rows:
        d = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
            elif v is not None:
                d[k] = v
            else:
                d[k] = None
        result.append(d)
    return result


async def get_markets() -> list[dict]:
    rows = await _pool.fetch("""
        WITH latest AS (
            SELECT DISTINCT ON (market_id)
                market_id, price, best_bid, best_ask
            FROM polymarket.price_snapshots
            ORDER BY market_id, ts DESC
        )
        SELECT
            m.id, m.question, m.start_ts, m.end_ts,
            m.resolved, m.outcome, m.yes_outcome, m.no_outcome,
            (m.end_ts <= NOW())                           AS window_ended,
            (m.start_ts <= NOW() AND m.end_ts > NOW())    AS is_live,
            (m.start_ts > NOW())                          AS is_upcoming,
            COUNT(t.id)::int          AS trade_count,
            COALESCE(SUM(t.size), 0)::float AS total_volume,
            l.price::float            AS last_price,
            l.best_bid::float         AS last_bid,
            l.best_ask::float         AS last_ask
        FROM polymarket.markets m
        LEFT JOIN polymarket.trades t ON t.market_id = m.id
        LEFT JOIN latest l ON l.market_id = m.id
        GROUP BY m.id, m.question, m.start_ts, m.end_ts,
                 m.resolved, m.outcome, m.yes_outcome, m.no_outcome,
                 l.price, l.best_bid, l.best_ask
        ORDER BY m.start_ts DESC
    """)
    return _fmt(rows)


async def get_market(market_id: int) -> Optional[dict]:
    row = await _pool.fetchrow(
        """
        SELECT *,
            (end_ts <= NOW())                        AS window_ended,
            (start_ts <= NOW() AND end_ts > NOW())   AS is_live,
            (start_ts > NOW())                       AS is_upcoming
        FROM polymarket.markets WHERE id = $1
        """,
        market_id,
    )
    if not row:
        return None
    return _fmt([row])[0]


async def get_price_snapshots(market_id: int) -> list[dict]:
    rows = await _pool.fetch("""
        SELECT
            ts,
            price::float     AS price,
            best_bid::float  AS best_bid,
            best_ask::float  AS best_ask,
            spread::float    AS spread
        FROM polymarket.price_snapshots
        WHERE market_id = $1
        ORDER BY ts
    """, market_id)
    return _fmt(rows)


async def get_trades(market_id: int) -> list[dict]:
    rows = await _pool.fetch("""
        SELECT ts, outcome, side, price::float AS price, size::float AS size
        FROM polymarket.trades
        WHERE market_id = $1
        ORDER BY ts
    """, market_id)
    return _fmt(rows)


async def get_volume_buckets(market_id: int) -> list[dict]:
    rows = await _pool.fetch("""
        SELECT
            date_trunc('minute', ts) +
                (FLOOR(EXTRACT(epoch FROM ts - date_trunc('minute', ts)) / 15)
                 * INTERVAL '15 seconds') AS bucket,
            outcome,
            SUM(size)::float AS volume
        FROM polymarket.trades
        WHERE market_id = $1
        GROUP BY bucket, outcome
        ORDER BY bucket, outcome
    """, market_id)
    return _fmt(rows)


async def get_book_depth(market_id: int, token_id: str) -> Optional[dict]:
    row = await _pool.fetchrow("""
        SELECT bids, asks
        FROM polymarket.book_checkpoints
        WHERE market_id = $1 AND token_id = $2
        ORDER BY ts DESC
        LIMIT 1
    """, market_id, token_id)
    if not row:
        return None
    return {"bids": row["bids"], "asks": row["asks"]}


async def get_data_gaps(market_id: int, threshold_sec: int = 5) -> list[dict]:
    """Find time ranges in this market where snapshot polling stopped for
    more than `threshold_sec` (collector should be polling at 1Hz).
    Returns [{start, end, dur_sec}, ...]."""
    rows = await _pool.fetch("""
        WITH ordered AS (
            SELECT ts, LAG(ts) OVER (ORDER BY ts) AS prev_ts
            FROM polymarket.price_snapshots
            WHERE market_id = $1
        )
        SELECT prev_ts AS start, ts AS gap_end,
               EXTRACT(EPOCH FROM (ts - prev_ts))::int AS dur_sec
        FROM ordered
        WHERE prev_ts IS NOT NULL
          AND EXTRACT(EPOCH FROM (ts - prev_ts)) > $2
        ORDER BY prev_ts
    """, market_id, threshold_sec)
    return _fmt(rows)


async def health_age() -> dict:
    """Return seconds-since-last for snapshots and trades. Used by /health."""
    row = await _pool.fetchrow("""
        SELECT
          EXTRACT(EPOCH FROM (NOW() - MAX(ps.ts)))::int AS snap_age,
          EXTRACT(EPOCH FROM (NOW() - MAX(t.ts)))::int  AS trade_age
        FROM polymarket.price_snapshots ps
        FULL JOIN polymarket.trades t ON FALSE
    """)
    return {
        "snap_age_sec":  row["snap_age"]  if row and row["snap_age"]  is not None else None,
        "trade_age_sec": row["trade_age"] if row and row["trade_age"] is not None else None,
    }


async def get_delta_summary(market_id: int) -> dict:
    row = await _pool.fetchrow("""
        SELECT
            COUNT(*)                                           AS total,
            COUNT(*) FILTER (WHERE size = 0)                  AS removals,
            COUNT(*) FILTER (WHERE side = 'BUY' AND size > 0) AS bid_adds,
            COUNT(*) FILTER (WHERE side = 'SELL' AND size > 0) AS ask_adds
        FROM polymarket.book_deltas
        WHERE market_id = $1
    """, market_id)
    return dict(row) if row else {}
