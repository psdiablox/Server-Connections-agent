from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import require_user
from ..db import pool
from ..schemas import (
    BookSnapshot,
    HeatmapResponse,
    Market,
    OrderStats,
    Outcome,
    Tick,
    Trade,
)

router = APIRouter(prefix="/api", tags=["markets"], dependencies=[Depends(require_user)])


async def _load_market(market_id: int) -> dict:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT m.*, n.slug AS network_slug, c.slug AS coin_slug
            FROM core.markets m
            JOIN core.networks n ON n.id = m.network_id
            LEFT JOIN core.coins c ON c.id = m.coin_id
            WHERE m.id = $1
            """,
            market_id,
        )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "market not found")
    return dict(row)


async def _load_outcomes(market_id: int) -> list[Outcome]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, label, external_token_id FROM core.market_outcomes "
            "WHERE market_id = $1 ORDER BY label",
            market_id,
        )
    return [
        Outcome(
            id=r["id"],
            label=r["label"],
            external_token_id=r["external_token_id"],
        )
        for r in rows
    ]


def _outcome_id_by_label(outcomes: list[Outcome], label: str) -> Optional[int]:
    for o in outcomes:
        if o.label == label:
            return o.id
    return None


@router.get("/markets/{market_id}", response_model=Market)
async def get_market(market_id: int) -> Market:
    m = await _load_market(market_id)
    outcomes = await _load_outcomes(market_id)
    return Market(
        id=m["id"],
        network_slug=m["network_slug"],
        coin_slug=m["coin_slug"],
        external_id=m["external_id"],
        kind=m["kind"],
        question=m["question"],
        period_seconds=m["period_seconds"],
        strike=float(m["strike"]) if m["strike"] is not None else None,
        starts_at=m["starts_at"],
        ends_at=m["ends_at"],
        resolved_at=m["resolved_at"],
        status=m["status"],
        resolution=m["resolution"],
        total_volume=float(m["total_volume"]) if m["total_volume"] is not None else None,
        traders=m["traders"],
        last_yes=float(m["last_yes"]) if m["last_yes"] is not None else None,
        last_no=float(m["last_no"]) if m["last_no"] is not None else None,
        outcomes=outcomes,
    )


@router.get("/markets/{market_id}/ticks", response_model=list[Tick])
async def get_ticks(
    market_id: int,
    bucket_seconds: int = Query(5, ge=1, le=300, alias="bucket"),
) -> list[Tick]:
    """Combined timeseries: yes/no probability (mid of YES outcome book) + base coin price.
    Bucketed by `bucket` seconds across the market window."""
    m = await _load_market(market_id)
    outcomes = await _load_outcomes(market_id)
    yes_id = _outcome_id_by_label(outcomes, "YES")
    no_id = _outcome_id_by_label(outcomes, "NO")
    starts_at = m["starts_at"]
    ends_at = m["ends_at"]
    if not starts_at or not ends_at:
        return []

    bucket = timedelta(seconds=bucket_seconds)
    async with pool().acquire() as conn:
        yes_rows = await conn.fetch(
            """
            SELECT time_bucket($1, ts) AS t,
                   AVG(mid) AS mid, AVG(last) AS last
            FROM polymarket.price_snapshots
            WHERE market_id = $2 AND outcome_id = $3
              AND ts >= $4 AND ts <= $5
            GROUP BY t ORDER BY t
            """,
            bucket,
            market_id,
            yes_id,
            starts_at,
            ends_at,
        ) if yes_id else []
        no_rows = await conn.fetch(
            """
            SELECT time_bucket($1, ts) AS t,
                   AVG(mid) AS mid, AVG(last) AS last
            FROM polymarket.price_snapshots
            WHERE market_id = $2 AND outcome_id = $3
              AND ts >= $4 AND ts <= $5
            GROUP BY t ORDER BY t
            """,
            bucket,
            market_id,
            no_id,
            starts_at,
            ends_at,
        ) if no_id else []
        coin_id = m["coin_id"]
        coin_rows = await conn.fetch(
            """
            SELECT time_bucket($1, ts) AS t, AVG(price) AS price
            FROM polymarket.coin_prices
            WHERE coin_id = $2 AND ts >= $3 AND ts <= $4
            GROUP BY t ORDER BY t
            """,
            bucket,
            coin_id,
            starts_at,
            ends_at,
        ) if coin_id else []

    yes_map = {r["t"]: float(r["mid"] or r["last"] or 0) for r in yes_rows if (r["mid"] or r["last"])}
    no_map = {r["t"]: float(r["mid"] or r["last"] or 0) for r in no_rows if (r["mid"] or r["last"])}
    coin_map = {r["t"]: float(r["price"]) for r in coin_rows if r["price"] is not None}

    keys = sorted(set(yes_map) | set(no_map) | set(coin_map))
    ticks: list[Tick] = []
    for t in keys:
        ticks.append(
            Tick(
                t=t,
                base_price=coin_map.get(t),
                yes=yes_map.get(t),
                no=no_map.get(t),
            )
        )
    return ticks


@router.get("/markets/{market_id}/trades", response_model=list[Trade])
async def get_trades(
    market_id: int,
    limit: int = Query(2000, ge=1, le=10000),
) -> list[Trade]:
    outcomes = await _load_outcomes(market_id)
    label_by_id = {o.id: o.label for o in outcomes}

    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ts, outcome_id, side, price, size
            FROM polymarket.trades
            WHERE market_id = $1
            ORDER BY ts ASC
            LIMIT $2
            """,
            market_id,
            limit,
        )
    return [
        Trade(
            t=r["ts"],
            outcome=label_by_id.get(r["outcome_id"], "?"),
            side=r["side"],
            price=float(r["price"]),
            size=float(r["size"]),
        )
        for r in rows
    ]


@router.get("/markets/{market_id}/book/snapshot", response_model=BookSnapshot)
async def get_book_snapshot(
    market_id: int,
    at: Optional[datetime] = None,
    outcome: str = Query("YES"),
) -> BookSnapshot:
    outcomes = await _load_outcomes(market_id)
    outcome_id = _outcome_id_by_label(outcomes, outcome.upper())
    if outcome_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "outcome not found")
    target = at or datetime.now(tz=timezone.utc)

    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT ts, bids, asks
            FROM polymarket.book_snapshots
            WHERE market_id = $1 AND outcome_id = $2 AND ts <= $3
            ORDER BY ts DESC LIMIT 1
            """,
            market_id,
            outcome_id,
            target,
        )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no snapshot")
    return BookSnapshot(
        t=row["ts"],
        outcome=outcome.upper(),
        bids=row["bids"],
        asks=row["asks"],
    )


@router.get("/markets/{market_id}/book/heatmap", response_model=HeatmapResponse)
async def get_book_heatmap(
    market_id: int,
    levels: int = Query(80, ge=10, le=200),
    buckets: int = Query(80, ge=10, le=200),
    outcome: str = Query("YES"),
) -> HeatmapResponse:
    """Pre-bin book_snapshots into a (levels x buckets) grid of total resting size.
    Price levels span 0..1 (probability). Time buckets span [starts_at, ends_at]."""
    m = await _load_market(market_id)
    outcomes = await _load_outcomes(market_id)
    outcome_id = _outcome_id_by_label(outcomes, outcome.upper())
    if outcome_id is None or not m["starts_at"] or not m["ends_at"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "missing window or outcome")

    starts_at: datetime = m["starts_at"]
    ends_at: datetime = m["ends_at"]
    span_seconds = max(1.0, (ends_at - starts_at).total_seconds())
    bucket_seconds = span_seconds / buckets

    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ts, bids, asks
            FROM polymarket.book_snapshots
            WHERE market_id = $1 AND outcome_id = $2
              AND ts >= $3 AND ts <= $4
            ORDER BY ts
            """,
            market_id,
            outcome_id,
            starts_at,
            ends_at,
        )

    grid: list[list[float]] = [[0.0] * buckets for _ in range(levels)]
    for r in rows:
        ts: datetime = r["ts"]
        bucket_idx = min(buckets - 1, int((ts - starts_at).total_seconds() / bucket_seconds))
        if bucket_idx < 0:
            continue
        for side in ("bids", "asks"):
            for entry in r[side] or []:
                try:
                    price = float(entry[0])
                    size = float(entry[1])
                except (TypeError, ValueError, IndexError):
                    continue
                if not (0.0 <= price <= 1.0):
                    continue
                lvl = min(levels - 1, int(price * levels))
                grid[lvl][bucket_idx] += size

    return HeatmapResponse(
        levels=levels,
        buckets=buckets,
        starts_at=starts_at,
        ends_at=ends_at,
        grid=grid,
    )


@router.get("/markets/{market_id}/order-stats", response_model=OrderStats)
async def get_order_stats(market_id: int) -> OrderStats:
    outcomes = await _load_outcomes(market_id)
    label_by_id = {o.id: o.label for o in outcomes}

    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT outcome_id, side, COUNT(*) AS c, SUM(size) AS vol,
                   MAX(size) AS biggest, AVG(size) AS avg_size
            FROM polymarket.trades
            WHERE market_id = $1
            GROUP BY outcome_id, side
            """,
            market_id,
        )

    counts = {"YES": {"BUY": 0, "SELL": 0}, "NO": {"BUY": 0, "SELL": 0}}
    vols = {"YES": {"BUY": 0.0, "SELL": 0.0}, "NO": {"BUY": 0.0, "SELL": 0.0}}
    biggest = 0.0
    total_size = 0.0
    total_count = 0
    for r in rows:
        label = label_by_id.get(r["outcome_id"])
        side = r["side"]
        if label not in counts or side not in ("BUY", "SELL"):
            continue
        counts[label][side] = r["c"]
        vols[label][side] = float(r["vol"] or 0)
        biggest = max(biggest, float(r["biggest"] or 0))
        total_count += r["c"]
        total_size += float(r["vol"] or 0)

    return OrderStats(
        yes_buy_count=counts["YES"]["BUY"],
        yes_sell_count=counts["YES"]["SELL"],
        no_buy_count=counts["NO"]["BUY"],
        no_sell_count=counts["NO"]["SELL"],
        yes_buy_volume=vols["YES"]["BUY"],
        yes_sell_volume=vols["YES"]["SELL"],
        no_buy_volume=vols["NO"]["BUY"],
        no_sell_volume=vols["NO"]["SELL"],
        largest_trade=biggest or None,
        avg_trade=(total_size / total_count) if total_count else None,
    )
