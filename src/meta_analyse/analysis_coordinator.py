"""Compose footprint and tape analytics without bypassing quality gates."""
from __future__ import annotations
from .footprint_engine import FootprintEngine
from .tape_velocity import TapeVelocity
from .market_clock import MarketClock

class AnalysisCoordinator:
    def __init__(self,tick_sizes):
        self.footprints=FootprintEngine(tick_sizes)
        self.clock=MarketClock()
        self.tapes={symbol:TapeVelocity(tick) for symbol,tick in tick_sizes.items()}
        self.levels={}

    def set_level(self,symbol,price):
        if symbol not in self.tapes:
            raise ValueError("unknown symbol")
        self.levels[symbol]=price
        self.tapes[symbol].reset()

    async def execution(self,event,*,contiguous):
        self.clock.observe("trades",event.symbol,event.timestamp_ms,trusted=contiguous)
        footprint=self.footprints.execution(event,contiguous=contiguous)
        level=self.levels.get(event.symbol)
        tape=None
        if level is not None:
            tape=self.tapes[event.symbol].add(event,level_price=level,contiguous=contiguous)
        return footprint,tape

    async def gap(self,symbols,reason):
        for symbol in symbols:
            self.clock.gap("trades",symbol)
            self.footprints.gap(symbol)
            if symbol in self.tapes:
                self.tapes[symbol].reset()

    async def book(self,symbol,book,timestamp_ms):
        self.clock.observe("orderbook",symbol,timestamp_ms,trusted=book.valid)

    async def book_gap(self,symbols,reason):
        for symbol in symbols:
            self.clock.gap("orderbook",symbol)
