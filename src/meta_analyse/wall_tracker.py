"""Orderbook wall observations, without claiming to prove spoofing intent."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class WallObservation:
    price: Decimal
    side: str
    notional: Decimal
    lifetime_ms: int
    vanished_without_execution_evidence: bool
    confidence: str

class WallTracker:
    def __init__(self, min_notional=Decimal("100000"), max_age_ms=3000):
        self.min_notional=Decimal(min_notional)
        self.max_age_ms=max_age_ms
        self.active={}
        self.last_ts=None

    def reset(self):
        self.active.clear()
        self.last_ts=None

    def observe(self, book, received_ms: int):
        if not book.valid:
            self.reset()
            return []
        if self.last_ts is not None and received_ms < self.last_ts:
            self.reset()
            return []
        self.last_ts=received_ms
        current={}
        for side,levels in (("bid",book.bids),("ask",book.asks)):
            for price,size in levels.items():
                value=price*size
                if value>=self.min_notional:
                    current[(side,price)]=value
        warnings=[]
        for key,(first,notional) in self.active.items():
            if key not in current:
                lifetime=received_ms-first
                if lifetime <= self.max_age_ms:
                    warnings.append(WallObservation(key[1],key[0],notional,lifetime,
                                                    True,"unverified_cancellation_or_execution"))
        self.active={key:(self.active[key][0] if key in self.active else received_ms,value)
                     for key,value in current.items()}
        return warnings
