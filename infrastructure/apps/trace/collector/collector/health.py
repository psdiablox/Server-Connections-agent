"""Heartbeat helpers used by the WS loops to record their up/down state.

Every healthy WS session emits a heartbeat every HEARTBEAT_SECONDS. A
session that drops emits an explicit 'down' row with the failure reason.
The API turns gaps in 'up' rows during a market window into outage bands.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from .db import pool

log = logging.getLogger("trace.health")

HEARTBEAT_SECONDS = 10


async def emit(source: str, status: str, reason: Optional[str] = None) -> None:
    try:
        async with pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO core.collection_health (source, ts, status, reason)
                VALUES ($1, now(), $2, $3)
                ON CONFLICT (source, ts) DO NOTHING
                """,
                source, status, reason,
            )
    except Exception:
        log.exception("failed to write heartbeat for %s", source)


class Heartbeat:
    """Background task that emits 'up' rows every HEARTBEAT_SECONDS while
    the surrounding WS session is alive."""

    def __init__(self, source: str):
        self.source = source
        self._task: Optional[asyncio.Task] = None

    async def _loop(self) -> None:
        while True:
            await emit(self.source, "up")
            await asyncio.sleep(HEARTBEAT_SECONDS)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name=f"hb-{self.source}")

    async def stop(self, reason: Optional[str] = None) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if reason is not None:
            await emit(self.source, "down", reason)
