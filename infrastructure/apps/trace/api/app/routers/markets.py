import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ..auth import require_user
from ..db import pool
from ..schemas import (
    BookSnapshot,
    HeatmapResponse,
    Market,
    OrderStats,
    Outage,
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
    prev_id: Optional[int] = None
    next_id: Optional[int] = None
    if m["starts_at"] is not None and m["coin_id"] is not None and m["period_seconds"] is not None:
        async with pool().acquire() as conn:
            prev_id = await conn.fetchval(
                """SELECT id FROM core.markets
                   WHERE network_id = $1 AND coin_id = $2 AND period_seconds = $3
                     AND starts_at < $4
                   ORDER BY starts_at DESC LIMIT 1""",
                m["network_id"], m["coin_id"], m["period_seconds"], m["starts_at"],
            )
            next_id = await conn.fetchval(
                """SELECT id FROM core.markets
                   WHERE network_id = $1 AND coin_id = $2 AND period_seconds = $3
                     AND starts_at > $4
                   ORDER BY starts_at ASC LIMIT 1""",
                m["network_id"], m["coin_id"], m["period_seconds"], m["starts_at"],
            )
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
        prev_market_id=prev_id,
        next_market_id=next_id,
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
    limit: int = Query(20000, ge=1, le=100000),
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None, alias="to"),
) -> list[Trade]:
    """By default returns trades that occurred *during the market's resolution
    window* — Polymarket BTC markets trade for ~24 h leading up to the window,
    so without filtering you'd see thousands of out-of-window trades and the
    chart would clip the in-window ones via LIMIT. ?from= and ?to= override."""
    m = await _load_market(market_id)
    outcomes = await _load_outcomes(market_id)
    label_by_id = {o.id: o.label for o in outcomes}
    start = from_ or m["starts_at"]
    end = to or m["ends_at"]

    async with pool().acquire() as conn:
        if start is not None and end is not None:
            rows = await conn.fetch(
                """SELECT ts, outcome_id, side, price, size
                   FROM polymarket.trades
                   WHERE market_id = $1 AND ts >= $2 AND ts <= $3
                   ORDER BY ts ASC LIMIT $4""",
                market_id, start, end, limit,
            )
        else:
            rows = await conn.fetch(
                """SELECT ts, outcome_id, side, price, size
                   FROM polymarket.trades WHERE market_id = $1
                   ORDER BY ts ASC LIMIT $2""",
                market_id, limit,
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
) -> HeatmapResponse:
    """Time-weighted, per-side, per-outcome resting-depth heatmap.

    Each book_snapshot's state is treated as in-effect from its own timestamp
    until the next snapshot's timestamp (or window end). For each (level,
    bucket) cell, a snapshot's resting size at that level contributes
    `size * overlap_seconds` where overlap is the time the state was in
    effect inside that bucket.

    This decouples cell brightness from snapshot frequency: a $100 ask
    sitting at 30¢ for 60 s contributes 6,000 size-seconds whether 5 or 500
    snapshots covered the minute.

    Returns four grids (levels x buckets), units = size-seconds:
      yes_buy  = bids on the YES token
      yes_sell = asks on the YES token
      no_buy   = bids on the NO  token
      no_sell  = asks on the NO  token
    """
    m = await _load_market(market_id)
    outcomes = await _load_outcomes(market_id)
    yes_id = _outcome_id_by_label(outcomes, "YES")
    no_id = _outcome_id_by_label(outcomes, "NO")
    if not m["starts_at"] or not m["ends_at"] or (yes_id is None and no_id is None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "missing window or outcomes")

    starts_at: datetime = m["starts_at"]
    ends_at: datetime = m["ends_at"]
    span_seconds = max(1.0, (ends_at - starts_at).total_seconds())
    bucket_seconds = span_seconds / buckets

    yes_buy = [[0.0] * buckets for _ in range(levels)]
    yes_sell = [[0.0] * buckets for _ in range(levels)]
    no_buy = [[0.0] * buckets for _ in range(levels)]
    no_sell = [[0.0] * buckets for _ in range(levels)]

    outcome_ids = [oid for oid in (yes_id, no_id) if oid is not None]
    async with pool().acquire() as conn:
        # In-window snapshots
        rows = await conn.fetch(
            """
            SELECT outcome_id, ts, bids, asks
            FROM polymarket.book_snapshots
            WHERE market_id = $1
              AND outcome_id = ANY($2::bigint[])
              AND ts >= $3 AND ts <= $4
            ORDER BY outcome_id, ts
            """,
            market_id, outcome_ids, starts_at, ends_at,
        )
        # Pre-window seed: latest snapshot per outcome BEFORE starts_at — gives
        # us the book state at window open instead of letting early buckets
        # look dim until the first in-window snapshot arrives.
        seeds = await conn.fetch(
            """
            SELECT DISTINCT ON (outcome_id) outcome_id, ts, bids, asks
            FROM polymarket.book_snapshots
            WHERE market_id = $1
              AND outcome_id = ANY($2::bigint[])
              AND ts < $3
            ORDER BY outcome_id, ts DESC
            """,
            market_id, outcome_ids, starts_at,
        )

    # Group rows by outcome (already ordered by outcome_id, ts in the SQL).
    by_outcome: dict[int, list] = {}
    for r in rows:
        by_outcome.setdefault(r["outcome_id"], []).append(r)
    # Prepend the seed snapshot per outcome with its ts clamped to starts_at,
    # so its state is treated as in-effect from window start.
    for s in seeds:
        seed = {"outcome_id": s["outcome_id"], "ts": starts_at, "bids": s["bids"], "asks": s["asks"]}
        existing = by_outcome.setdefault(s["outcome_id"], [])
        existing.insert(0, seed)

    for outcome_id, snaps in by_outcome.items():
        is_yes = outcome_id == yes_id
        bids_grid = yes_buy if is_yes else no_buy
        asks_grid = yes_sell if is_yes else no_sell

        for i, snap in enumerate(snaps):
            # The book state from this snapshot is in effect until the next
            # snapshot's ts (or window end for the last one).
            state_start = max(snap["ts"], starts_at)
            state_end_raw = snaps[i + 1]["ts"] if i + 1 < len(snaps) else ends_at
            state_end = min(state_end_raw, ends_at)
            if state_end <= state_start:
                continue

            # Buckets that overlap this state's [state_start, state_end].
            start_b = max(0, int((state_start - starts_at).total_seconds() / bucket_seconds))
            end_b = min(buckets - 1, int((state_end - starts_at).total_seconds() / bucket_seconds))

            # Pre-extract level/size pairs once per snap (avoid reparsing per bucket).
            bid_levels: list[tuple[int, float]] = []
            for entry in snap["bids"] or []:
                try:
                    price = float(entry[0]); size = float(entry[1])
                except (TypeError, ValueError, IndexError):
                    continue
                if 0.0 <= price <= 1.0:
                    bid_levels.append((min(levels - 1, int(price * levels)), size))
            ask_levels: list[tuple[int, float]] = []
            for entry in snap["asks"] or []:
                try:
                    price = float(entry[0]); size = float(entry[1])
                except (TypeError, ValueError, IndexError):
                    continue
                if 0.0 <= price <= 1.0:
                    ask_levels.append((min(levels - 1, int(price * levels)), size))

            for b in range(start_b, end_b + 1):
                bucket_start = starts_at + timedelta(seconds=b * bucket_seconds)
                bucket_end = starts_at + timedelta(seconds=(b + 1) * bucket_seconds)
                overlap_start = max(state_start, bucket_start)
                overlap_end = min(state_end, bucket_end)
                overlap_secs = (overlap_end - overlap_start).total_seconds()
                if overlap_secs <= 0:
                    continue
                for lvl, size in bid_levels:
                    bids_grid[lvl][b] += size * overlap_secs
                for lvl, size in ask_levels:
                    asks_grid[lvl][b] += size * overlap_secs

    return HeatmapResponse(
        levels=levels, buckets=buckets,
        starts_at=starts_at, ends_at=ends_at,
        yes_buy=yes_buy, yes_sell=yes_sell, no_buy=no_buy, no_sell=no_sell,
    )


@router.get("/markets/{market_id}/outages", response_model=list[Outage])
async def get_outages(market_id: int) -> list[Outage]:
    """Two kinds of outages are reported, both as red bands on the chart:

    1. Source-level: gaps in the heartbeat written by a collector subsystem
       (polymarket-clob, binance) — used when the whole subsystem went silent.
       Threshold: 30 s without a heartbeat.

    2. Market-level: gaps in the 1 Hz price_snapshots stream for this specific
       market. Catches the case where the WS stayed alive overall but lost
       this particular market's subscription. Threshold: 5 s without a snap.
    """
    m = await _load_market(market_id)
    starts_at = m["starts_at"]
    ends_at = m["ends_at"]
    if not starts_at or not ends_at:
        return []

    outages: list[Outage] = []
    async with pool().acquire() as conn:
        # 1 — heartbeat gaps per source ----------------------------------
        sources = await conn.fetch(
            "SELECT DISTINCT source FROM core.collection_health "
            "WHERE ts >= ($1::timestamptz - INTERVAL '5 minutes') AND ts <= ($2::timestamptz + INTERVAL '5 minutes')",
            starts_at, ends_at,
        )
        SRC_GAP = 30
        for src_row in sources:
            src = src_row["source"]
            rows = await conn.fetch(
                """SELECT ts, status, reason FROM core.collection_health
                   WHERE source = $1
                     AND ts >= ($2::timestamptz - INTERVAL '5 minutes')
                     AND ts <= ($3::timestamptz + INTERVAL '5 minutes')
                   ORDER BY ts""",
                src, starts_at, ends_at,
            )
            prev_ts = None
            prev_reason = None
            for r in rows:
                ts = r["ts"]
                if prev_ts is not None:
                    gap = (ts - prev_ts).total_seconds()
                    if gap > SRC_GAP:
                        s = max(prev_ts, starts_at)
                        e = min(ts, ends_at)
                        if e > s:
                            outages.append(Outage(
                                source=src,
                                start=s, end=e,
                                reason=prev_reason or f"{src} silent for {gap:.0f}s",
                                duration_seconds=(e - s).total_seconds(),
                            ))
                prev_ts = ts
                prev_reason = r["reason"] if r["status"] == "down" else None
            if prev_ts is not None and prev_ts < ends_at - timedelta(seconds=SRC_GAP):
                s = max(prev_ts, starts_at)
                if s < ends_at:
                    outages.append(Outage(
                        source=src,
                        start=s, end=ends_at,
                        reason=prev_reason or f"{src} silent at window end",
                        duration_seconds=(ends_at - s).total_seconds(),
                    ))

        # 2 — per-market price_snapshot gaps -----------------------------
        snap_rows = await conn.fetch(
            """SELECT ts FROM polymarket.price_snapshots
               WHERE market_id = $1 AND ts >= $2 AND ts <= $3
               ORDER BY ts""",
            market_id, starts_at, ends_at,
        )
        MARKET_GAP = 5
        if not snap_rows:
            outages.append(Outage(
                source="market-data",
                start=starts_at, end=ends_at,
                reason="no price snapshot recorded for this market in the window — collector may have missed subscription",
                duration_seconds=(ends_at - starts_at).total_seconds(),
            ))
        else:
            prev = starts_at
            first_ts = snap_rows[0]["ts"]
            if (first_ts - starts_at).total_seconds() > MARKET_GAP:
                outages.append(Outage(
                    source="market-data",
                    start=starts_at, end=first_ts,
                    reason=f"no price data captured for first {(first_ts - starts_at).total_seconds():.0f}s — collector subscribed late or pre-window data not retained",
                    duration_seconds=(first_ts - starts_at).total_seconds(),
                ))
            prev = first_ts
            for r in snap_rows[1:]:
                ts = r["ts"]
                gap = (ts - prev).total_seconds()
                if gap > MARKET_GAP:
                    outages.append(Outage(
                        source="market-data",
                        start=prev, end=ts,
                        reason=f"no price snapshot for {gap:.0f}s — Polymarket WS likely dropped this market's subscription",
                        duration_seconds=gap,
                    ))
                prev = ts
            trail = (ends_at - prev).total_seconds()
            if trail > MARKET_GAP:
                outages.append(Outage(
                    source="market-data",
                    start=prev, end=ends_at,
                    reason=f"no price snapshot for last {trail:.0f}s of window — subscription lost before close",
                    duration_seconds=trail,
                ))

    # Merge overlapping market-data + source outages? Keep separate so the
    # user can see which layer failed — they get distinct bands.
    outages.sort(key=lambda o: (o.start, o.source))
    return outages


@router.get("/markets/{market_id}/order-stats", response_model=OrderStats)
async def get_order_stats(market_id: int) -> OrderStats:
    m = await _load_market(market_id)
    outcomes = await _load_outcomes(market_id)
    label_by_id = {o.id: o.label for o in outcomes}
    start = m["starts_at"]
    end = m["ends_at"]

    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT outcome_id, side, COUNT(*) AS c, SUM(size) AS vol,
                   MAX(size) AS biggest, AVG(size) AS avg_size
            FROM polymarket.trades
            WHERE market_id = $1
              AND ($2::timestamptz IS NULL OR ts >= $2)
              AND ($3::timestamptz IS NULL OR ts <= $3)
            GROUP BY outcome_id, side
            """,
            market_id, start, end,
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


# ---------------------------------------------------------------------------
# CSV exports — one file per kind, scoped to the market's resolution window.
# Cookies authenticate (the router-level dependency above), browser saves the
# file via Content-Disposition.
# ---------------------------------------------------------------------------

def _export_filename(network_slug: str, coin_slug: Optional[str], starts_at: datetime, ends_at: datetime, kind: str) -> str:
    s = starts_at.astimezone(timezone.utc)
    e = ends_at.astimezone(timezone.utc)
    parts = [
        network_slug or "network",
        coin_slug or "coin",
        s.strftime("%Y-%m-%d"),
        s.strftime("%H-%M"),
        e.strftime("%H-%M"),
        "UTC",
        kind,
    ]
    return "_".join(parts) + ".csv"


def _csv_response(rows: list[list], header: list[str], filename: str) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/markets/{market_id}/export/trades")
async def export_trades(market_id: int) -> Response:
    """Every fill in the market's resolution window, one row per trade."""
    m = await _load_market(market_id)
    outcomes = await _load_outcomes(market_id)
    label_by_id = {o.id: o.label for o in outcomes}
    starts_at, ends_at = m["starts_at"], m["ends_at"]
    if starts_at is None or ends_at is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "market has no window")

    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT ts, outcome_id, side, price, size,
                      taker_address, maker_address, tx_hash, external_id
               FROM polymarket.trades
               WHERE market_id = $1 AND ts >= $2 AND ts <= $3
               ORDER BY ts""",
            market_id, starts_at, ends_at,
        )
    out = []
    for r in rows:
        price = float(r["price"]); size = float(r["size"])
        out.append([
            r["ts"].astimezone(timezone.utc).isoformat(),
            label_by_id.get(r["outcome_id"], ""),
            r["side"],
            price,
            size,
            price * size,
            r["taker_address"] or "",
            r["maker_address"] or "",
            r["tx_hash"] or "",
            r["external_id"] or "",
        ])
    header = ["ts_utc", "outcome", "side", "price", "size", "value_usd",
              "taker_address", "maker_address", "tx_hash", "external_id"]
    return _csv_response(out, header,
                         _export_filename(m["network_slug"], m["coin_slug"], starts_at, ends_at, "trades"))


@router.get("/markets/{market_id}/export/book-snapshots")
async def export_book_snapshots(market_id: int) -> Response:
    """Every L2 order-book snapshot, expanded to one row per (snap, side, level)."""
    m = await _load_market(market_id)
    outcomes = await _load_outcomes(market_id)
    label_by_id = {o.id: o.label for o in outcomes}
    starts_at, ends_at = m["starts_at"], m["ends_at"]
    if starts_at is None or ends_at is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "market has no window")

    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT ts, outcome_id, bids, asks, hash
               FROM polymarket.book_snapshots
               WHERE market_id = $1 AND ts >= $2 AND ts <= $3
               ORDER BY ts, outcome_id""",
            market_id, starts_at, ends_at,
        )
    out = []
    for r in rows:
        ts_iso = r["ts"].astimezone(timezone.utc).isoformat()
        outcome = label_by_id.get(r["outcome_id"], "")
        snap_hash = r["hash"] or ""
        for entry in r["bids"] or []:
            try:
                price = float(entry[0]); size = float(entry[1])
            except (TypeError, ValueError, IndexError):
                continue
            out.append([ts_iso, outcome, "bid", price, size, snap_hash])
        for entry in r["asks"] or []:
            try:
                price = float(entry[0]); size = float(entry[1])
            except (TypeError, ValueError, IndexError):
                continue
            out.append([ts_iso, outcome, "ask", price, size, snap_hash])
    header = ["ts_utc", "outcome", "side", "price", "size", "snapshot_hash"]
    return _csv_response(out, header,
                         _export_filename(m["network_slug"], m["coin_slug"], starts_at, ends_at, "book-snapshots"))


@router.get("/markets/{market_id}/export/price-snapshots")
async def export_price_snapshots(market_id: int) -> Response:
    """1 Hz price snapshots (best_bid, best_ask, mid, last) per outcome."""
    m = await _load_market(market_id)
    outcomes = await _load_outcomes(market_id)
    label_by_id = {o.id: o.label for o in outcomes}
    starts_at, ends_at = m["starts_at"], m["ends_at"]
    if starts_at is None or ends_at is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "market has no window")

    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT ts, outcome_id, best_bid, best_ask, mid, last
               FROM polymarket.price_snapshots
               WHERE market_id = $1 AND ts >= $2 AND ts <= $3
               ORDER BY ts, outcome_id""",
            market_id, starts_at, ends_at,
        )
    out = []
    for r in rows:
        out.append([
            r["ts"].astimezone(timezone.utc).isoformat(),
            label_by_id.get(r["outcome_id"], ""),
            float(r["best_bid"]) if r["best_bid"] is not None else "",
            float(r["best_ask"]) if r["best_ask"] is not None else "",
            float(r["mid"]) if r["mid"] is not None else "",
            float(r["last"]) if r["last"] is not None else "",
        ])
    header = ["ts_utc", "outcome", "best_bid", "best_ask", "mid", "last_trade_price"]
    return _csv_response(out, header,
                         _export_filename(m["network_slug"], m["coin_slug"], starts_at, ends_at, "price-snapshots"))
