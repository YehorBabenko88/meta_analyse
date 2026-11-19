"""Rolling trade velocity and signed volume around verified price levels."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from market_profile_math import tape_velocity_metrics

@dataclass(frozen=True)
class TapeSnapshot:
    trades_per_second: Decimal
    notional_per_second: Decimal
    buy_notional: Decimal
    sell_notional: Decimal
    distance_ticks: Decimal
    trusted: bool

class TapeVelocity:
    def __init__(self, tick_size: Decimal, window_ms=5000, proximity_ticks=20):
        if tick_size<=0 or window_ms<=0:
            raise ValueError("invalid tape settings")
        self.tick_size=tick_size
        self.window_ms=window_ms
        self.proximity_ticks=Decimal(proximity_ticks)
        self.events=deque()
        self.last_ms=None

    def reset(self):
        self.events.clear()
        self.last_ms=None

    def add(self,execution,level_price:Decimal,*,contiguous:bool):
        if not contiguous:
            self.reset()
            return TapeSnapshot(Decimal(0),Decimal(0),Decimal(0),Decimal(0),
                                abs(execution.price-level_price)/self.tick_size,False)
        if self.last_ms is not None and execution.timestamp_ms < self.last_ms:
            self.reset()
            return TapeSnapshot(Decimal(0),Decimal(0),Decimal(0),Decimal(0),
                                abs(execution.price-level_price)/self.tick_size,False)
        self.last_ms=execution.timestamp_ms
        self.events.append(execution)
        cutoff=execution.timestamp_ms-self.window_ms
        while self.events and self.events[0].timestamp_ms<cutoff:
            self.events.popleft()
        rows = [(event.timestamp_ms,event.price,event.quantity,event.taker_side)
                for event in self.events]
        trades,notional,buys,sells,distance=tape_velocity_metrics(
            rows,level_price,self.tick_size,self.window_ms,self.proximity_ticks,
            execution.timestamp_ms,observed_price=execution.price)
        return TapeSnapshot(trades,notional,buys,sells,distance,
                            distance<=self.proximity_ticks)
