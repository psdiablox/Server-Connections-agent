"""Binance BTCUSDT spot trade websocket — underlying spot price.

We bucket incoming trades into 1s rows (last price wins per second per source)
to keep storage bounded while preserving the second-level resolution the
analysis chart needs.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import orjson
import websockets

from .config import settings
from .db import pool

log = logging.getLogger("trace.binance")


async def _coin_id(slug: str) -> Optional[int]:
    async with pool().acquire() as conn:
        return await conn.fetchval("SELECT id FROM core.coins WHERE slug=$1", slug)


async def binance_loop() -> None:
    coin_id = await _coin_id("btc")
    if not coin_id:
        log.error("btc coin missing in core.coins; run seed migration")
        return

    pending: dict[int, float] = {}  # second-bucket -> last price
    flush_lock = asyncio.Lock()

    async def flush() -> None:
        async with flush_lock:
            if not pending:
                return
            rows = [
                (coin_id, datetime.fromtimestamp(sec, tz=timezone.utc), price, "binance")
                for sec, price in pending.items()
            ]
            pending.clear()
        async with pool().acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO polymarket.coin_prices (coin_id, ts, price, source)
                VALUES ($1,$2,$3,$4)
                ON CONFLICT DO NOTHING
                """,
                rows,
            )

    async def flusher():
        while True:
            await asyncio.sleep(1)
            try:
                await flush()
            except Exception:
                log.exception("binance flush error")

    flush_task = asyncio.create_task(flusher())

    try:
        while True:
            try:
                log.info("binance ws connecting")
                async with websockets.connect(
                    settings.binance_ws,
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:
                    while True:
                        raw = await ws.recv()
                        try:
                            msg = orjson.loads(raw)
                        except orjson.JSONDecodeError:
                            continue
                        # Trade message: { e:"trade", T:ms, p:"price", q:"qty", ... }
                        if msg.get("e") != "trade":
                            continue
                        try:
                            ts_ms = int(msg["T"])
                            price = float(msg["p"])
                        except (KeyError, ValueError, TypeError):
                            continue
                        sec = ts_ms // 1000
                        pending[sec] = price
            except Exception:
                log.exception("binance ws error; reconnecting in 5s")
                await asyncio.sleep(5)
    finally:
        flush_task.cancel()
