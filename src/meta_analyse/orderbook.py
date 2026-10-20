"""Bybit orderbook snapshot/delta state with fail-closed sequence validation."""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal

@dataclass
class OrderBook:
    symbol: str
    bids: dict[Decimal, Decimal] = field(default_factory=dict)
    asks: dict[Decimal, Decimal] = field(default_factory=dict)
    update_id: int | None = None
    sequence: int | None = None
    valid: bool = False

    def reset(self):
        self.bids.clear()
        self.asks.clear()
        self.update_id = None
        self.sequence = None
        self.valid = False

    def apply(self, message: dict):
        if not isinstance(message, dict) or not isinstance(message.get("data"), dict):
            self.reset()
            return False
        data = message["data"]
        if data.get("s") != self.symbol:
            self.reset()
            return False
        kind = message.get("type")
        uid = data.get("u")
        seq = data.get("seq")
        if type(uid) is not int or type(seq) is not int or uid < 0 or seq < 0:
            self.reset()
            return False
        if kind == "snapshot":
            self.reset()
            try:
                self._levels(data)
            except (ValueError, TypeError, ArithmeticError):
                self.reset()
                return False
            self.update_id = uid
            self.sequence = seq
            self.valid = self._healthy()
            if not self.valid:
                self.reset()
            return self.valid
        if kind != "delta" or not self.valid or self.update_id is None or self.sequence is None:
            self.reset()
            return False
        # Bybit may skip update IDs in streamed messages; require strictly
        # increasing update IDs and cross-sequence, not falsely assume +1.
        if uid <= self.update_id or seq <= self.sequence:
            self.reset()
            return False
        try:
            self._levels(data)
        except (ValueError, TypeError, ArithmeticError):
            self.reset()
            return False
        self.update_id = uid
        self.sequence = seq
        self.valid = self._healthy()
        if not self.valid:
            self.reset()
        return self.valid

    def _levels(self, data):
        for field, book in (("b",self.bids),("a",self.asks)):
            for price_text,size_text in data.get(field,[]):
                price, size = Decimal(str(price_text)), Decimal(str(size_text))
                if not price.is_finite() or not size.is_finite() or price <= 0 or size < 0:
                    raise ValueError("invalid orderbook level")
                if size == 0:
                    book.pop(price,None)
                else:
                    book[price]=size

    def _healthy(self):
        return bool(self.bids and self.asks and max(self.bids)<min(self.asks))
