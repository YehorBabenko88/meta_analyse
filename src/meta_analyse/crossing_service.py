"""Event-driven, fail-closed crossing cleanup for app-owned MetaScalp levels."""
from __future__ import annotations
import asyncio
from decimal import Decimal
from .crossing_quality import CrossingObservation

class CrossingService:
    def __init__(self, level_sync, connection_for_symbol):
        self.sync=level_sync
        self.connection_for_symbol=connection_for_symbol
        self.last={}
        self.locks={}

    async def execution(self,event,*,contiguous:bool):
        symbol=event.symbol
        lock=self.locks.setdefault(symbol,asyncio.Lock())
        async with lock:
            previous=self.last.get(symbol)
            current=Decimal(event.price)
            # Never bridge reconnects, reorderings, or unverified continuity.
            if not contiguous:
                self.last.pop(symbol,None)
                return 0
            self.last[symbol]=current
            if previous is None:
                return 0
            connection=self.connection_for_symbol(symbol)
            if connection is None:
                return 0
            try:
                return await self.sync.crossed(connection,symbol,previous,current)
            except Exception:
                # Terminal state uncertain: stop assuming continuity; reread on next valid tick.
                self.last.pop(symbol,None)
                raise

    def gap(self,symbol):
        self.last.pop(symbol,None)
