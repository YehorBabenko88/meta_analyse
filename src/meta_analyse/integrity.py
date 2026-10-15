"""Strict execution ordering and minute provenance, no invented ticks."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from .raw_trades import RawExecution
from .core import Trade, new_minute, floor_minute

@dataclass
class Quality:
    contiguous: bool = True
    reason: str = "observed"
    last_timestamp_ms: int | None = None
    duplicates: int = 0
    out_of_order: int = 0

class ExecutionAggregator:
    def __init__(self, tick_size: Decimal):
        self.tick_size = tick_size
        self.quality: dict[str, Quality] = {}
        self.minutes = {}
        self.closed = []
        self.seen: set[tuple[str, str]] = set()

    def gap(self, symbols: list[str], reason: str):
        for symbol in symbols:
            q = self.quality.setdefault(symbol, Quality())
            q.contiguous = False
            q.reason = reason
            self.minutes.pop(symbol, None)

    def accept(self, e: RawExecution):
        key = (e.symbol, e.execution_id)
        q = self.quality.setdefault(e.symbol, Quality())
        if key in self.seen:
            q.duplicates += 1
            return None
        if q.last_timestamp_ms is not None and e.timestamp_ms < q.last_timestamp_ms:
            q.out_of_order += 1
            q.contiguous = False
            q.reason = "out_of_order"
            self.minutes.pop(e.symbol, None)
            return None
        timestamp = datetime.fromtimestamp(e.timestamp_ms / 1000, timezone.utc)
        t = Trade(e.symbol, timestamp, e.price, e.quantity, e.taker_side)
        current = self.minutes.get(e.symbol)
        slot = floor_minute(timestamp)
        if current and current.start != slot:
            if slot - current.start == __import__('datetime').timedelta(minutes=1) and q.contiguous and current.complete:
                self.closed.append((e.symbol, current, "observed_contiguous"))
            else:
                q.contiguous = False
                q.reason = "minute_gap"
            current = None
        if current is None:
            current = new_minute(t, self.tick_size, complete=False)
            self.minutes[e.symbol] = current
        else:
            current.add(t)
        self.seen.add(key)
        q.last_timestamp_ms = e.timestamp_ms
        return current
