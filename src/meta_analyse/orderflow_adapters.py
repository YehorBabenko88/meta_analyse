"""Read-only order-flow adapters; no network or database dependencies."""
from collections import deque
from decimal import Decimal
from .orderflow_metrics import Trade


def from_records(records):
    """Normalize historical records without assuming source completeness."""
    for row in records:
        side = str(row.get("side", "unknown")).lower()
        if side not in ("buy", "sell", "unknown"):
            raise ValueError("unsupported aggressor side")
        timestamp = row["timestamp_ms"]
        if isinstance(timestamp, bool) or not isinstance(timestamp, int):
            raise ValueError("timestamp_ms must be an integer")
        trade = Trade(
            timestamp_ms=timestamp,
            price=Decimal(str(row["price"])),
            volume=Decimal(str(row["volume"])),
            side=side,
        )
        if not trade.price.is_finite() or trade.price <= 0:
            raise ValueError("price must be finite and positive")
        if not trade.volume.is_finite() or trade.volume < 0:
            raise ValueError("volume must be finite and nonnegative")
        yield trade


class StreamingTrades:
    """Bounded, single-owner stream; loss explicitly invalidates continuity."""

    def __init__(self, capacity=10000):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self._trades = deque(maxlen=capacity)
        self.dropped = 0
        self.gaps = 0

    @property
    def continuous(self):
        return self.dropped == 0 and self.gaps == 0

    def append(self, trade):
        if not isinstance(trade, Trade):
            raise TypeError("expected normalized Trade")
        if len(self._trades) == self._trades.maxlen:
            self.dropped += 1
        self._trades.append(trade)

    def mark_gap(self):
        """A reported feed gap must not be mistaken for complete coverage."""
        self.gaps += 1

    def snapshot(self):
        return tuple(self._trades)

    def reset(self):
        self._trades.clear()
        self.dropped = 0
        self.gaps = 0
