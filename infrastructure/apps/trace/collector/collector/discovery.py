"""Polymarket BTC 5-min market discovery.

The schedule is fixed: every 5 minutes starting at HH:00 UTC. We don't need
to search broadly — for any boundary timestamp T we ask gamma for markets
whose startDate matches T exactly, narrow the result to BTC + 5-min, and
upsert the match.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

import aiohttp

from .config import settings
from .db import pool

log = logging.getLogger("trace.discovery")

# How many upcoming windows to ensure are in the catalogue at any time.
LOOKAHEAD = 6
# How many recently-passed windows to backfill on startup.
LOOKBEHIND = 2


def boundaries(now: Optional[datetime] = None) -> list[datetime]:
    now = (now or datetime.now(tz=timezone.utc)).replace(second=0, microsecond=0)
    minute = now.minute - (now.minute % 5)
    base = now.replace(minute=minute)
    return [base + timedelta(minutes=5 * i) for i in range(-LOOKBEHIND, LOOKAHEAD + 1)]


def _is_btc_5min(item: dict) -> bool:
    """Heuristic: title mentions BTC/Bitcoin AND endDate - startDate ≈ 5 minutes."""
    title = (item.get("question") or item.get("title") or "").lower()
    if "btc" not in title and "bitcoin" not in title:
        return False
    try:
        start = datetime.fromisoformat(item["startDate"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(item["endDate"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return False
    span = (end - start).total_seconds()
    return abs(span - settings.btc_window_seconds) <= 5


def _parse_outcomes(item: dict) -> list[tuple[str, str]]:
    """Returns [(label, token_id), …]."""
    raw_outcomes = item.get("outcomes")
    raw_tokens = item.get("clobTokenIds")
    if isinstance(raw_outcomes, str):
        raw_outcomes = json.loads(raw_outcomes)
    if isinstance(raw_tokens, str):
        raw_tokens = json.loads(raw_tokens)
    if not raw_outcomes or not raw_tokens:
        return []
    return list(zip(raw_outcomes, raw_tokens))


async def _fetch_at_boundary(session: aiohttp.ClientSession, boundary: datetime) -> list[dict]:
    iso = boundary.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    after = (boundary - timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
    before = (boundary + timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
    params = {
        "start_date_min": after,
        "start_date_max": before,
        "active": "true",
        "closed": "false",
        "archived": "false",
        "limit": 100,
    }
    url = f"{settings.polymarket_gamma_url}/markets"
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        if resp.status != 200:
            log.warning("gamma %s -> %s", iso, resp.status)
            return []
        return await resp.json()


async def _upsert_market(item: dict) -> Optional[int]:
    """Insert/update one Polymarket market and its outcomes. Returns market_id."""
    outcomes = _parse_outcomes(item)
    if len(outcomes) != 2:
        return None
    try:
        starts_at = datetime.fromisoformat(item["startDate"].replace("Z", "+00:00"))
        ends_at = datetime.fromisoformat(item["endDate"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None

    title = item.get("question") or item.get("title") or ""
    # Strike: try meta fields, else parse from question ("close above $X")
    strike = None
    for key in ("strikePrice", "strike", "marketResolutionThreshold"):
        if key in item and item[key] is not None:
            try:
                strike = float(item[key])
                break
            except (TypeError, ValueError):
                pass
    if strike is None:
        import re
        m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", title)
        if m:
            try:
                strike = float(m.group(1).replace(",", ""))
            except ValueError:
                pass

    external_id = str(item.get("id") or item.get("conditionId") or item.get("slug") or "")
    if not external_id:
        return None

    async with pool().acquire() as conn:
        async with conn.transaction():
            network_id = await conn.fetchval("SELECT id FROM core.networks WHERE slug = 'polymarket'")
            coin_id = await conn.fetchval("SELECT id FROM core.coins WHERE slug = 'btc'")
            if not network_id or not coin_id:
                log.error("polymarket/btc rows missing in core; run seed migration")
                return None

            row = await conn.fetchrow(
                """
                INSERT INTO core.markets
                    (network_id, coin_id, external_id, kind, question, period_seconds,
                     strike, starts_at, ends_at, status, meta)
                VALUES ($1,$2,$3,'binary-window',$4,$5,$6,$7,$8,'upcoming',$9)
                ON CONFLICT (network_id, external_id) DO UPDATE
                  SET question = EXCLUDED.question,
                      strike = COALESCE(core.markets.strike, EXCLUDED.strike),
                      starts_at = EXCLUDED.starts_at,
                      ends_at = EXCLUDED.ends_at,
                      meta = core.markets.meta || EXCLUDED.meta,
                      updated_at = now()
                RETURNING id
                """,
                network_id,
                coin_id,
                external_id,
                title,
                settings.btc_window_seconds,
                strike,
                starts_at,
                ends_at,
                json.dumps({"slug": item.get("slug"), "conditionId": item.get("conditionId")}),
            )
            market_id = row["id"]

            for label, token_id in outcomes:
                await conn.execute(
                    """
                    INSERT INTO core.market_outcomes (market_id, label, external_token_id)
                    VALUES ($1,$2,$3)
                    ON CONFLICT (market_id, label) DO UPDATE
                      SET external_token_id = EXCLUDED.external_token_id
                    """,
                    market_id,
                    label.upper(),
                    str(token_id),
                )
    return market_id


async def discovery_loop(market_signal: asyncio.Event) -> None:
    """Every DISCOVERY_INTERVAL, ensure each scheduled boundary has a row."""
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                added = 0
                for b in boundaries():
                    async with pool().acquire() as conn:
                        existing = await conn.fetchval(
                            """
                            SELECT 1 FROM core.markets m
                            JOIN core.networks n ON n.id = m.network_id
                            JOIN core.coins c ON c.id = m.coin_id
                            WHERE n.slug='polymarket' AND c.slug='btc'
                              AND m.period_seconds=$1 AND m.starts_at=$2
                            """,
                            settings.btc_window_seconds,
                            b,
                        )
                    if existing:
                        continue
                    items = await _fetch_at_boundary(session, b)
                    for it in items:
                        if not _is_btc_5min(it):
                            continue
                        mid = await _upsert_market(it)
                        if mid:
                            log.info("discovered market %s @ %s", mid, b.isoformat())
                            added += 1
                            break  # one per boundary
                if added:
                    market_signal.set()
            except Exception:
                log.exception("discovery error")
            await asyncio.sleep(settings.discovery_interval_seconds)
