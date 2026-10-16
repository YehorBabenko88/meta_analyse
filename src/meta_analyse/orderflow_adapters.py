"""Read-only order-flow adapters; no network or database dependencies."""
from decimal import Decimal
from .orderflow_metrics import Trade


def from_records(records):
    """Normalize verified trade records; caller owns source verification."""
    for row in records:
        side = str(row.get("side", "unknown")).lower()
        if side not in ("buy", "sell", "unknown"):
            raise ValueError("unsupported aggressor side")
        yield Trade(
            timestamp_ms=int(row["timestamp_ms"]),
            price=Decimal(str(row["price"])),
            volume=Decimal(str(row["volume"])),
            side=side,
        )


class StreamingTrades:
    """Bounded ingestion buffer; consume snapshots without altering producers."""

    def __init__(self, capacity=10000):
        from collections import deque
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._trades = deque(maxlen=capacity)
        self.dropped = 0

    def append(self, trade):
        if len(self._trades) == self._trades.maxlen:
            self.dropped += 1
        self._trades.append(trade)

    def snapshot(self):
        return tuple(self._trades)
