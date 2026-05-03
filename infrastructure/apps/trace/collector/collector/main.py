import asyncio
import logging
import signal
import sys

from .binance import binance_loop
from .clob import clob_loop
from .config import settings
from .db import close_pool, init_pool
from .discovery import discovery_loop
from .status import status_loop

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("trace.collector")


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
