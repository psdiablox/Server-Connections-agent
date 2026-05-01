from __future__ import annotations
import json
from datetime import datetime
from typing import Optional

import asyncpg

import config

_pool: Optional[asyncpg.Pool] = None


async def init() -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        config.DB_URL,
        min_size=2,
        max_size=10,
        init=_register_codecs,
    )


async def _register_codecs(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


def _conn():
    return _pool.acquire()


async def upsert_market(
    condition_id: str,
    yes_token_id: str,
    no_token_id: str,
    yes_outcome: str,
    no_outcome: str,
    question: str,
    start_ts: datetime,
    end_ts: datetime,
) -> int:
    async with _conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO polymarket.markets
                (condition_id, yes_token_id, no_token_id, yes_outcome, no_outcome, question, start_ts, end_ts)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (condition_id) DO UPDATE
                SET yes_token_id = EXCLUDED.yes_token_id,
                    no_token_id  = EXCLUDED.no_token_id
            RETURNING id
            """,
            condition_id, yes_token_id, no_token_id,
            yes_outcome, no_outcome, question, start_ts, end_ts,
        )
        return row["id"]


async def mark_resolved(condition_id: str, outcome: str) -> None:
    async with _conn() as conn:
        await conn.execute(
            "UPDATE polymarket.markets SET resolved=TRUE, outcome=$1 WHERE condition_id=$2",
            outcome, condition_id,
        )


async def insert_price_snapshot(
    ts: datetime,
    market_id: int,
    price: Optional[float],
    best_bid: Optional[str],
    best_ask: Optional[str],
) -> None:
    spread = None
    try:
        if best_bid and best_ask:
            spread = float(best_ask) - float(best_bid)
    except (TypeError, ValueError):
        pass

    async with _conn() as conn:
        await conn.execute(
            """
            INSERT INTO polymarket.price_snapshots
                (ts, market_id, price, best_bid, best_ask, spread)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT DO NOTHING
            """,
            ts,
            market_id,
            float(price) if price is not None else None,
            float(best_bid) if best_bid else None,
            float(best_ask) if best_ask else None,
            float(spread)   if spread   else None,
        )


async def insert_trade(
    ts: datetime,
    market_id: int,
    token_id: str,
    outcome: str,
    price: str,
    size: str,
    side: str,
) -> None:
    async with _conn() as conn:
        await conn.execute(
            """
            INSERT INTO polymarket.trades
                (ts, market_id, token_id, outcome, price, size, side)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            ts, market_id, token_id, outcome,
            float(price), float(size), side,
        )


async def insert_book_checkpoint(
    ts: datetime,
    market_id: int,
    token_id: str,
    bids: list,
    asks: list,
) -> None:
    async with _conn() as conn:
        await conn.execute(
            """
            INSERT INTO polymarket.book_checkpoints
                (ts, market_id, token_id, bids, asks)
            VALUES ($1, $2, $3, $4, $5)
            """,
            ts, market_id, token_id, bids, asks,
        )


async def insert_book_deltas(rows: list[tuple]) -> None:
    # row = (ts, market_id, token_id, side, price, size)
    if not rows:
        return
    async with _conn() as conn:
        await conn.executemany(
            """
            INSERT INTO polymarket.book_deltas
                (ts, market_id, token_id, side, price, size)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            rows,
        )
