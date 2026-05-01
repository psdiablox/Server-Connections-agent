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


async def main() -> None:
    await db.init()
    log.info("database pool ready")

    state = CollectorState()

    tasks = [
        asyncio.create_task(discover_loop(state),    name="discover"),
        asyncio.create_task(ws_loop(state),           name="ws"),
        asyncio.create_task(price_poll_loop(state),   name="poller"),
    ]

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

    for t in done:
        if exc := t.exception():
            log.error("task '%s' crashed: %s", t.get_name(), exc, exc_info=exc)

    for t in pending:
        t.cancel()


if __name__ == "__main__":
    asyncio.run(main())
