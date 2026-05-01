import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import auth
import queries

DB_URL = os.environ["DATABASE_URL"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await queries.init(DB_URL)
    yield


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": error}
    )


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if auth.check_credentials(username, password):
        token = auth.create_session()
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("session", token, httponly=True, samesite="lax")
        return resp
    return RedirectResponse("/login?error=1", status_code=303)


@app.get("/logout")
async def logout(session: str = Depends(auth.require_auth)):
    auth.revoke_session(session)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session")
    return resp


# ── Page routes ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse("/markets", status_code=303)


@app.get("/markets", response_class=HTMLResponse)
async def markets_page(request: Request, _=Depends(auth.require_auth)):
    markets = await queries.get_markets()
    return templates.TemplateResponse(
        "markets.html", {"request": request, "markets": markets}
    )


@app.get("/markets/{market_id}", response_class=HTMLResponse)
async def market_detail(
    market_id: int, request: Request, _=Depends(auth.require_auth)
):
    market = await queries.get_market(market_id)
    if not market:
        return RedirectResponse("/markets", status_code=303)
    return templates.TemplateResponse(
        "market.html", {"request": request, "market": market}
    )


# ── API routes (JSON, consumed by charts) ─────────────────────────────────────

@app.get("/api/markets/{market_id}/snapshots")
async def api_snapshots(market_id: int, _=Depends(auth.require_auth)):
    return await queries.get_price_snapshots(market_id)


@app.get("/api/markets/{market_id}/trades")
async def api_trades(market_id: int, _=Depends(auth.require_auth)):
    return await queries.get_trades(market_id)


@app.get("/api/markets/{market_id}/volume")
async def api_volume(market_id: int, _=Depends(auth.require_auth)):
    return await queries.get_volume_buckets(market_id)


@app.get("/api/markets/{market_id}/depth")
async def api_depth(market_id: int, _=Depends(auth.require_auth)):
    market = await queries.get_market(market_id)
    if not market:
        return JSONResponse({})
    return await queries.get_book_depth(market_id, market["yes_token_id"])


@app.get("/api/markets/{market_id}/deltas")
async def api_deltas(market_id: int, _=Depends(auth.require_auth)):
    return await queries.get_delta_summary(market_id)
