import asyncio
import logging
import sys

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

    state = CollectorState()

    await asyncio.gather(
        resilient(discover_loop,    state, "discover"),
        resilient(ws_loop,          state, "ws"),
        resilient(price_poll_loop,  state, "poller"),
    )


if __name__ == "__main__":
    asyncio.run(main())
