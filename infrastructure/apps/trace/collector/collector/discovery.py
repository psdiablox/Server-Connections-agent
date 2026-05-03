"""Polymarket BTC 5-min market discovery.

Polymarket runs recurring "Bitcoin Up or Down — <date>, HH:MMAM-HH:MMAM ET"
markets. Each one resolves at a fixed top-of-5-minute boundary; trading opens
~24 hours ahead. For TRACE we treat the 5-minute *resolution window* as the
"window" — `starts_at = endDate - 5min`, `ends_at = endDate`.

Strategy: every DISCOVERY_INTERVAL_SECONDS, ask gamma for active "Bitcoin Up
or Down" markets (a small list — typically the next ~30 still open), filter
to ones whose endDate sits on a 5-minute boundary, upsert.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiohttp

from .config import settings
from .db import pool

log = logging.getLogger("trace.discovery")

USER_AGENT = "trace-collector/0.1 (+https://data.pserenlo.com)"

# Title regex: "Bitcoin Up or Down - <date>, <time>-<time> ET"
TITLE_RE = re.compile(r"\bbitcoin\s+up\s+or\s+down\b", re.IGNORECASE)


def _parse_iso(s: str) -> Optional[datetime]:
    try:
        # gamma returns "2026-05-04T15:55:00Z" or with microseconds
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError):
        return None


def _is_btc_5min(item: dict) -> tuple[bool, Optional[datetime], Optional[datetime]]:
    """Return (matches, starts_at, ends_at) where the timestamps describe the
    5-min resolution window — NOT the long trading window."""
    title = item.get("question") or item.get("title") or ""
    if not TITLE_RE.search(title):
        return False, None, None
    end = _parse_iso(item.get("endDate"))
    if not end:
        return False, None, None
    # endDate must align to a 5-minute boundary.
    if end.second != 0 or end.microsecond != 0 or (end.minute % 5) != 0:
        return False, None, None
    starts = end - timedelta(seconds=settings.btc_window_seconds)
    return True, starts, end


def _parse_outcomes(item: dict) -> list[tuple[str, str]]:
    raw_outcomes = item.get("outcomes")
    raw_tokens = item.get("clobTokenIds")
    if isinstance(raw_outcomes, str):
        try:
            raw_outcomes = json.loads(raw_outcomes)
        except json.JSONDecodeError:
            raw_outcomes = None
    if isinstance(raw_tokens, str):
        try:
            raw_tokens = json.loads(raw_tokens)
        except json.JSONDecodeError:
            raw_tokens = None
    if not raw_outcomes or not raw_tokens:
        return []
    return list(zip(raw_outcomes, raw_tokens))


def _parse_strike(item: dict) -> Optional[float]:
    for key in ("strikePrice", "strike", "marketResolutionThreshold"):
        v = item.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    title = item.get("question") or item.get("title") or ""
    m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", title)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


async def _fetch_active(session: aiohttp.ClientSession) -> list[dict]:
    """Pull every still-active market ending in [now - 10min, now + 26h].
    BTC up/down markets open ~24h before resolution, so this captures:
      - the live market (resolving in the next 5 min)
      - all upcoming markets created in the last 24h
      - markets that ended in the last 10 min (still 'active' in gamma's grace)
    Ordered by endDate ascending so we hit the live one first.
    """
    now = datetime.now(tz=timezone.utc)
    end_min = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_max = (now + timedelta(hours=26)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{settings.polymarket_gamma_url}/markets"
    params = {
        "active": "true",
        "closed": "false",
        "archived": "false",
        "end_date_min": end_min,
        "end_date_max": end_max,
        "order": "endDate",
        "ascending": "true",
        "limit": 500,
    }
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        if resp.status != 200:
            log.warning("gamma %s -> %s", url, resp.status)
            return []
        return await resp.json()


async def _upsert_market(item: dict, starts_at: datetime, ends_at: datetime) -> Optional[int]:
    outcomes = _parse_outcomes(item)
    if len(outcomes) != 2:
        return None
    external_id = str(item.get("id") or item.get("conditionId") or item.get("slug") or "")
    if not external_id:
        return None
    title = item.get("question") or item.get("title") or ""
    strike = _parse_strike(item)

    async with pool().acquire() as conn:
        async with conn.transaction():
            network_id = await conn.fetchval("SELECT id FROM core.networks WHERE slug='polymarket'")
            coin_id = await conn.fetchval("SELECT id FROM core.coins WHERE slug='btc'")
            if not network_id or not coin_id:
                log.error("polymarket/btc rows missing in core; check seed migration")
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
                RETURNING (xmax = 0) AS inserted, id
                """,
                network_id, coin_id, external_id, title,
                settings.btc_window_seconds, strike, starts_at, ends_at,
                json.dumps({"slug": item.get("slug"), "conditionId": item.get("conditionId")}),
            )
            inserted = row["inserted"]
            market_id = row["id"]
            for label, token_id in outcomes:
                await conn.execute(
                    """
                    INSERT INTO core.market_outcomes (market_id, label, external_token_id)
                    VALUES ($1,$2,$3)
                    ON CONFLICT (market_id, label) DO UPDATE
                      SET external_token_id = EXCLUDED.external_token_id
                    """,
                    market_id, label.upper(), str(token_id),
                )
    return market_id if inserted else None


async def discovery_loop(market_signal: asyncio.Event) -> None:
    log.info("discovery loop starting (interval=%ds)", settings.discovery_interval_seconds)
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                items = await _fetch_active(session)
                matches = 0
                added = 0
                for it in items:
                    ok, starts_at, ends_at = _is_btc_5min(it)
                    if not ok or starts_at is None or ends_at is None:
                        continue
                    matches += 1
                    new_id = await _upsert_market(it, starts_at, ends_at)
                    if new_id:
                        log.info("discovered market %s | %s -> %s", new_id, starts_at.isoformat(), ends_at.isoformat())
                        added += 1
                log.debug("discovery cycle: %d items, %d matched, %d new", len(items), matches, added)
                if added:
                    market_signal.set()
            except Exception:
                log.exception("discovery error")
            await asyncio.sleep(settings.discovery_interval_seconds)
