from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# ---- auth ----------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class Me(BaseModel):
    username: str


# ---- catalogue -----------------------------------------------------------

class Network(BaseModel):
    slug: str
    name: str
    kind: str
    color: Optional[str] = None
    tagline: Optional[str] = None
    enabled: bool
    sort_order: int
    meta: dict[str, Any] = {}


class Coin(BaseModel):
    slug: str
    symbol: str
    name: str
    color: Optional[str] = None
    base_price: Optional[float] = None
    enabled: bool = True
    meta: dict[str, Any] = {}


class Timeframe(BaseModel):
    id: str
    label: str
    seconds: int


# ---- markets / windows ---------------------------------------------------

class Outcome(BaseModel):
    id: int
    label: str
    external_token_id: Optional[str] = None


class Market(BaseModel):
    id: int
    network_slug: str
    coin_slug: Optional[str]
    external_id: str
    kind: str
    question: Optional[str]
    period_seconds: Optional[int]
    strike: Optional[float]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    resolved_at: Optional[datetime]
    status: str
    resolution: Optional[str]
    total_volume: Optional[float]
    traders: Optional[int]
    last_yes: Optional[float]
    last_no: Optional[float]
    outcomes: list[Outcome] = []


class WindowSummary(BaseModel):
    id: int
    external_id: str
    starts_at: datetime
    ends_at: datetime
    period_seconds: int
    strike: Optional[float]
    status: str
    resolution: Optional[str]
    total_volume: Optional[float]
    traders: Optional[int]
    last_yes: Optional[float]
    last_no: Optional[float]


class WindowList(BaseModel):
    items: list[WindowSummary]
    total: int
    counts: dict[str, int]


# ---- timeseries ----------------------------------------------------------

class Tick(BaseModel):
    t: datetime
    base_price: Optional[float]
    yes: Optional[float]
    no: Optional[float]


class Trade(BaseModel):
    t: datetime
    outcome: str
    side: str
    price: float
    size: float


class BookSnapshot(BaseModel):
    t: datetime
    outcome: str
    bids: list[list[float]]
    asks: list[list[float]]


class HeatmapResponse(BaseModel):
    levels: int
    buckets: int
    starts_at: datetime
    ends_at: datetime
    grid: list[list[float]]


class Outage(BaseModel):
    source: str
    start: datetime
    end: datetime
    reason: Optional[str] = None
    duration_seconds: float


class OrderStats(BaseModel):
    yes_buy_count: int
    yes_sell_count: int
    no_buy_count: int
    no_sell_count: int
    yes_buy_volume: float
    yes_sell_volume: float
    no_buy_volume: float
    no_sell_volume: float
    largest_trade: Optional[float]
    avg_trade: Optional[float]
