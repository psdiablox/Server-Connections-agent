from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional


@dataclass
class Market:
    db_id:        int
    condition_id: str
    yes_token_id: str   # first token  (e.g. "Up"   token)
    no_token_id:  str   # second token (e.g. "Down" token)
    yes_outcome:  str   # actual label, e.g. "Up" or "YES"
    no_outcome:   str   # actual label, e.g. "Down" or "NO"
    question:     str

    def outcome_for(self, token_id: str) -> str:
        return self.yes_outcome if token_id == self.yes_token_id else self.no_outcome


@dataclass
class OrderBook:
    bids:     dict[str, str] = field(default_factory=dict)  # price -> size
    asks:     dict[str, str] = field(default_factory=dict)
    best_bid: Optional[str]  = None
    best_ask: Optional[str]  = None

    def apply_snapshot(self, buys: list[dict], sells: list[dict]) -> None:
        self.bids = {e["price"]: e["size"] for e in buys  if "price" in e}
        self.asks = {e["price"]: e["size"] for e in sells if "price" in e}
        self._recompute()

    def apply_delta(
        self,
        side: str,
        price: str,
        size: str,
        best_bid: Optional[str] = None,
        best_ask: Optional[str] = None,
    ) -> None:
        target = self.bids if side == "BUY" else self.asks
        try:
            if not float(size):
                target.pop(price, None)
            else:
                target[price] = size
        except (ValueError, TypeError):
            pass

        # Prefer API-provided values; fall back to recompute
        if best_bid is not None:
            self.best_bid = best_bid
        if best_ask is not None:
            self.best_ask = best_ask
        if best_bid is None and best_ask is None:
            self._recompute()

    def _recompute(self) -> None:
        def to_dec(p: str) -> Decimal:
            try:
                return Decimal(p)
            except InvalidOperation:
                return Decimal(0)

        self.best_bid = max(self.bids, key=to_dec) if self.bids else None
        self.best_ask = min(self.asks, key=to_dec) if self.asks else None

    def sorted_snapshot(self) -> tuple[list[dict], list[dict]]:
        def to_dec(d: dict) -> Decimal:
            try:
                return Decimal(d["price"])
            except (InvalidOperation, KeyError):
                return Decimal(0)

        bids = sorted(
            [{"price": p, "size": s} for p, s in self.bids.items()],
            key=to_dec, reverse=True,
        )
        asks = sorted(
            [{"price": p, "size": s} for p, s in self.asks.items()],
            key=to_dec,
        )
        return bids, asks


class CollectorState:
    def __init__(self) -> None:
        self._markets:  dict[str, Market]    = {}  # condition_id -> Market
        self._by_token: dict[str, Market]    = {}  # token_id     -> Market
        self._books:    dict[str, OrderBook] = {}  # token_id     -> OrderBook

    def add_market(self, m: Market) -> None:
        self._markets[m.condition_id] = m
        self._by_token[m.yes_token_id] = m
        self._by_token[m.no_token_id]  = m
        self._books.setdefault(m.yes_token_id, OrderBook())
        self._books.setdefault(m.no_token_id,  OrderBook())

    def by_token(self, token_id: str) -> Optional[Market]:
        return self._by_token.get(token_id)

    def book(self, token_id: str) -> Optional[OrderBook]:
        return self._books.get(token_id)

    def known_conditions(self) -> set[str]:
        return set(self._markets.keys())

    def all_markets(self) -> list[Market]:
        return list(self._markets.values())

    def all_token_ids(self) -> list[str]:
        return list(self._books.keys())
