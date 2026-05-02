import asyncio
import logging
import sys
from datetime import datetime, timezone

import db
from state import CollectorState
from collector import discover_loop, ws_loop, price_poll_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


async def resilient(coro_fn, state, name):
    """Run a task loop, restarting it on crash with a short backoff."""
    while True:
        try:
            await coro_fn(state)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error("task '%s' crashed: %s — restarting in 10s", name, exc, exc_info=True)
            await asyncio.sleep(10)


async def main() -> None:
    await db.init()
    log.info("database pool ready")

    # ── Outage bookkeeping ────────────────────────────────────────────────
    # Close any rows from a previous run that crashed without closing.
    await db.outage_close_open()
    # If there's a gap between the last data event and now, record it as a
    # process_restart outage. NOW the chart will show a grey band exactly
    # over the time the collector wasn't running.
    last = await db.last_event_ts()
    if last is not None:
        gap = (datetime.now(timezone.utc) - last).total_seconds()
        if gap > 10:
            await db.outage_record(last, datetime.now(timezone.utc), "process_restart")
            log.info("recorded startup outage: %.1fs since last data event", gap)

    state = CollectorState()

    try:
        await asyncio.gather(
            resilient(discover_loop,    state, "discover"),
            resilient(ws_loop,          state, "ws"),
            resilient(price_poll_loop,  state, "poller"),
        )
    finally:
        # On clean shutdown, close any open outage so the next run starts clean.
        await db.outage_close_open()


if __name__ == "__main__":
    asyncio.run(main())
