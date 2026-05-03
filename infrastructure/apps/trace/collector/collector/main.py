import asyncio
import logging
import os
import signal
import sys
import time

from . import clob as clob_module
from .binance import binance_loop
from .clob import clob_loop
from .config import settings
from .db import close_pool, init_pool
from .discovery import discovery_loop
from .health import emit as emit_health
from .status import status_loop

# Liveness budget: if clob_loop hasn't progressed in this many seconds, force
# a process restart. clob_iteration_ts is updated on every successful WS
# recv() — that's our 'I'm alive and processing' pulse. If 60 s pass without
# a single message AND no clean reconnect happened, something is wedged.
CLOB_STALL_BUDGET = 60.0
LIVENESS_CHECK_INTERVAL = 20.0

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("trace.collector")


async def liveness_watchdog(stop: asyncio.Event) -> None:
    """Top-level safety net. If the clob_loop hasn't iterated in
    CLOB_STALL_BUDGET seconds, the loop is wedged (almost certainly inside an
    asyncio cancellation deadlock that no inner try/except can recover from).
    Write a 'down' marker to the health table so the chart shows the outage
    plainly, then os._exit(1). Docker's restart: unless-stopped brings us
    back in ~2 s — empirically this is faster than any in-process recovery
    and immune to whatever weird state the event loop got into."""
    log.info("liveness watchdog armed (budget=%.0fs)", CLOB_STALL_BUDGET)
    # Allow a generous startup grace before judging.
    await asyncio.sleep(LIVENESS_CHECK_INTERVAL)
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=LIVENESS_CHECK_INTERVAL)
            return
        except asyncio.TimeoutError:
            pass
        idle = time.monotonic() - clob_module.clob_iteration_ts
        if idle > CLOB_STALL_BUDGET:
            log.error(
                "LIVENESS WATCHDOG: clob_loop has not iterated in %.0fs "
                "(budget=%.0fs) — forcing process restart",
                idle, CLOB_STALL_BUDGET,
            )
            try:
                await asyncio.wait_for(
                    emit_health(
                        "polymarket-clob", "down",
                        f"liveness watchdog: clob_loop wedged for {idle:.0f}s, "
                        "process force-restarted",
                    ),
                    timeout=3.0,
                )
            except (asyncio.TimeoutError, Exception):
                log.warning("liveness watchdog: could not write down marker")
            log.error("exiting with code 1 — Docker will restart this container")
            os._exit(1)


async def main() -> None:
    await init_pool()
    log.info("collector starting")

    market_signal = asyncio.Event()
    market_signal.set()  # kick CLOB loop on first iteration

    stop = asyncio.Event()

    def handle_sig(*_args):
        log.info("signal received; shutting down")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with __import__("contextlib").suppress(NotImplementedError):
            loop.add_signal_handler(sig, handle_sig)

    tasks = [
        asyncio.create_task(discovery_loop(market_signal), name="discovery"),
        asyncio.create_task(clob_loop(market_signal), name="clob"),
        asyncio.create_task(binance_loop(), name="binance"),
        asyncio.create_task(status_loop(), name="status"),
        asyncio.create_task(liveness_watchdog(stop), name="liveness"),
    ]

    done, _ = await asyncio.wait(
        [*tasks, asyncio.create_task(stop.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    for t in tasks:
        t.cancel()
    for t in tasks:
        try:
            await t
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("task crashed")

    await close_pool()
    log.info("collector stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
