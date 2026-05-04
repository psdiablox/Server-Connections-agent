from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import require_user
from ..db import pool
from ..schemas import Coin, Network, Timeframe, WindowList, WindowSummary

router = APIRouter(prefix="/api", tags=["catalogue"], dependencies=[Depends(require_user)])


def _row_to_network(row) -> Network:
    return Network(
        slug=row["slug"],
        name=row["name"],
        kind=row["kind"],
        color=row["color"],
        tagline=row["tagline"],
        enabled=row["enabled"],
        sort_order=row["sort_order"],
        meta=row["meta"] or {},
    )


@router.get("/networks", response_model=list[Network])
async def list_networks() -> list[Network]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT slug, name, kind, color, tagline, enabled, sort_order, meta "
            "FROM core.networks ORDER BY sort_order, name"
        )
    return [_row_to_network(r) for r in rows]


@router.get("/networks/{slug}", response_model=Network)
async def get_network(slug: str) -> Network:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT slug, name, kind, color, tagline, enabled, sort_order, meta "
            "FROM core.networks WHERE slug = $1",
            slug,
        )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "network not found")
    return _row_to_network(row)


@router.get("/networks/{slug}/coins", response_model=list[Coin])
async def list_coins_for_network(slug: str) -> list[Coin]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.slug, c.symbol, c.name, c.color, c.base_price, c.meta,
                   COALESCE(nc.enabled, FALSE) AS enabled,
                   COALESCE(nc.sort_order, 0) AS sort_order
            FROM core.networks n
            JOIN core.network_coins nc ON nc.network_id = n.id
            JOIN core.coins c ON c.id = nc.coin_id
            WHERE n.slug = $1
            ORDER BY nc.sort_order, c.symbol
            """,
            slug,
        )
    return [
        Coin(
            slug=r["slug"],
            symbol=r["symbol"],
            name=r["name"],
            color=r["color"],
            base_price=float(r["base_price"]) if r["base_price"] is not None else None,
            enabled=r["enabled"],
            meta=r["meta"] or {},
        )
        for r in rows
    ]


_TIMEFRAMES = [
    Timeframe(id="5m", label="5 MIN", seconds=300),
    Timeframe(id="15m", label="15 MIN", seconds=900),
    Timeframe(id="1h", label="1 HOUR", seconds=3600),
    Timeframe(id="1d", label="1 DAY", seconds=86400),
]


@router.get("/networks/{slug}/coins/{coin}/timeframes", response_model=list[Timeframe])
async def list_timeframes(slug: str, coin: str) -> list[Timeframe]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT m.period_seconds
            FROM core.markets m
            JOIN core.networks n ON n.id = m.network_id
            JOIN core.coins c ON c.id = m.coin_id
            WHERE n.slug = $1 AND c.slug = $2 AND m.period_seconds IS NOT NULL
            """,
            slug,
            coin,
        )
    seen = {r["period_seconds"] for r in rows}
    if not seen:
        return _TIMEFRAMES
    return [tf for tf in _TIMEFRAMES if tf.seconds in seen] or _TIMEFRAMES


def _tf_to_seconds(tf: str) -> Optional[int]:
    return {"5m": 300, "15m": 900, "1h": 3600, "1d": 86400}.get(tf)


@router.get("/networks/{slug}/coins/{coin}/windows", response_model=WindowList)
async def list_windows(
    slug: str,
    coin: str,
    tf: str = Query("5m"),
    status_filter: str = Query("all", alias="status"),
    resolution: str = Query("all"),
    sort: str = Query("time"),
    direction: str = Query("desc", alias="dir"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> WindowList:
    period = _tf_to_seconds(tf)
    if period is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown timeframe")

    where = ["n.slug = $1", "c.slug = $2", "m.period_seconds = $3"]
    args: list = [slug, coin, period]
    if status_filter != "all":
        args.append(status_filter)
        where.append(f"m.status = ${len(args)}")
    if resolution != "all":
        args.append(resolution.upper())
        where.append(f"m.resolution = ${len(args)}")
    where_sql = " AND ".join(where)

    sort_columns = {
        "time": "m.starts_at",
        "vol": "m.total_volume",
        "traders": "m.traders",
        "trades": "m.trade_count",
        "largest": "m.largest_trade",
        "avg": "m.avg_trade",
        "strike": "m.strike",
        "close": "m.close_btc",
        "status": "m.status",
        "result": "m.last_yes",
        "coverage": "m.data_coverage_pct",
        "change": "((m.close_btc - m.strike) / NULLIF(m.strike, 0))",
    }
    column = sort_columns.get(sort, "m.starts_at")
    dir_sql = "ASC" if direction.lower() == "asc" else "DESC"
    nulls = "NULLS LAST" if dir_sql == "DESC" else "NULLS FIRST"
    order_sql = f"{column} {dir_sql} {nulls}"

    async with pool().acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM core.markets m "
            f"JOIN core.networks n ON n.id = m.network_id "
            f"JOIN core.coins c ON c.id = m.coin_id "
            f"WHERE {where_sql}",
            *args,
        )
        rows = await conn.fetch(
            f"""
            SELECT m.id, m.external_id, m.starts_at, m.ends_at, m.period_seconds,
                   m.strike, m.status, m.resolution, m.total_volume, m.traders,
                   m.last_yes, m.last_no, m.trade_count, m.largest_trade,
                   m.avg_trade, m.close_btc, m.data_coverage_pct
            FROM core.markets m
            JOIN core.networks n ON n.id = m.network_id
            JOIN core.coins c ON c.id = m.coin_id
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT ${len(args)+1} OFFSET ${len(args)+2}
            """,
            *args,
            limit,
            offset,
        )
        counts_rows = await conn.fetch(
            """
            SELECT m.status, COUNT(*) AS c
            FROM core.markets m
            JOIN core.networks n ON n.id = m.network_id
            JOIN core.coins c ON c.id = m.coin_id
            WHERE n.slug = $1 AND c.slug = $2 AND m.period_seconds = $3
            GROUP BY m.status
            """,
            slug,
            coin,
            period,
        )

    counts = {"all": total, "live": 0, "upcoming": 0, "ended": 0}
    for r in counts_rows:
        counts[r["status"]] = r["c"]

    items = [
        WindowSummary(
            id=r["id"],
            external_id=r["external_id"],
            starts_at=r["starts_at"],
            ends_at=r["ends_at"],
            period_seconds=r["period_seconds"],
            strike=float(r["strike"]) if r["strike"] is not None else None,
            status=r["status"],
            resolution=r["resolution"],
            total_volume=float(r["total_volume"]) if r["total_volume"] is not None else None,
            traders=r["traders"],
            last_yes=float(r["last_yes"]) if r["last_yes"] is not None else None,
            last_no=float(r["last_no"]) if r["last_no"] is not None else None,
            trade_count=r["trade_count"],
            largest_trade=float(r["largest_trade"]) if r["largest_trade"] is not None else None,
            avg_trade=float(r["avg_trade"]) if r["avg_trade"] is not None else None,
            close_btc=float(r["close_btc"]) if r["close_btc"] is not None else None,
            data_coverage_pct=float(r["data_coverage_pct"]) if r["data_coverage_pct"] is not None else None,
        )
        for r in rows
    ]
    return WindowList(items=items, total=total, counts=counts)
