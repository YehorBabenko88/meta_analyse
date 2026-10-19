"""Bounded multi-symbol footprint accumulation with explicit gaps."""
from __future__ import annotations
from collections import deque
from .footprint import Footprint

class FootprintEngine:
    def __init__(self,tick_sizes,interval_ms=60000,max_closed=500):
        if interval_ms<=0 or max_closed<=0:
            raise ValueError("invalid footprint retention")
        self.tick_sizes=tick_sizes
        self.interval_ms=interval_ms
        self.current={}
        self.closed=deque(maxlen=max_closed)

    def execution(self,event,*,contiguous):
        tick=self.tick_sizes.get(event.symbol)
        if tick is None:
            raise ValueError("unknown instrument")
        slot=(event.timestamp_ms//self.interval_ms)*self.interval_ms
        old=self.current.get(event.symbol)
        if old and slot<old.start_ms:
            old.trusted=False
            return None
        if old and slot!=old.start_ms:
            if slot-old.start_ms!=self.interval_ms:
                old.trusted=False
            self.closed.append(old)
            old=None
        if old is None:
            old=Footprint(event.symbol,slot,self.interval_ms,tick,trusted=bool(contiguous))
            self.current[event.symbol]=old
        old.add(event,contiguous=contiguous)
        return old

    def gap(self,symbol):
        old=self.current.pop(symbol,None)
        if old:
            old.trusted=False
            self.closed.append(old)
