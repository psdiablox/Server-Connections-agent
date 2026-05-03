import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from .config import settings
from .db import close_pool, init_pool
from .migrate import migrate_with_pool
from .routers import auth as auth_router
from .routers import health as health_router
from .routers import markets as markets_router
from .routers import networks as networks_router

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("trace.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await init_pool()
    await migrate_with_pool(pool)
    log.info("api ready")
    yield
    await close_pool()


app = FastAPI(
    title="TRACE API",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True}


app.include_router(auth_router.router)
app.include_router(health_router.router)
app.include_router(networks_router.router)
app.include_router(markets_router.router)
