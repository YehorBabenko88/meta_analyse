"""Explicitly separate durable exchange executions from unverified profile continuity."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

@dataclass(frozen=True)
class StreamHealth:
    symbol: str
    last_exchange_ms: int | None
    received: int
    rejected: int
    gap_count: int
    profile_trusted: bool

class HealthTracker:
    def __init__(self):
        self.received={}
        self.rejected={}
        self.gaps={}
        self.last={}

    def record(self, event):
        s=event.symbol
        self.received[s]=self.received.get(s,0)+1
        self.last[s]=max(self.last.get(s,0),event.timestamp_ms)

    def reject(self,symbol):
        self.rejected[symbol]=self.rejected.get(symbol,0)+1

    def gap(self,symbol):
        self.gaps[symbol]=self.gaps.get(symbol,0)+1

    def snapshot(self,symbol):
        return StreamHealth(symbol,self.last.get(symbol),self.received.get(symbol,0),
                            self.rejected.get(symbol,0),self.gaps.get(symbol,0),False)
