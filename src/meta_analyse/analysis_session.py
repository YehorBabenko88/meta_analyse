"""Offline-wirable Bybit ingestion and analysis; no terminal writes or exchange orders."""
from __future__ import annotations
import asyncio
from .pipeline import RawPipeline
from .market_collector import MarketCollector
from .analysis_coordinator import AnalysisCoordinator

class AnalysisSession:
    def __init__(self,store,exchange,tick_sizes,*,on_update=None,on_gap=None):
        self.analysis=AnalysisCoordinator(tick_sizes)
        self.on_update=on_update
        self.on_gap=on_gap
        self.raw=RawPipeline(store,tick_sizes,
                             on_execution=self._execution,on_gap=self._trade_gap)
        self.market=MarketCollector(store,exchange,
                                    on_book=self._book,on_gap=self._book_gap)
        self.started=False

    def select_level(self,symbol,price):
        self.analysis.set_level(symbol,price)

    async def _execution(self,event,*,contiguous):
        footprint,tape=await self.analysis.execution(event,contiguous=contiguous)
        if self.on_update:
            await self.on_update(event.symbol,footprint.snapshot(),tape)

    async def _trade_gap(self,symbols,reason):
        await self.analysis.gap(symbols,reason)
        if self.on_gap:
            await self.on_gap(symbols,reason)

    async def _book(self,symbol,book,timestamp_ms):
        await self.analysis.book(symbol,book,timestamp_ms)

    async def _book_gap(self,symbols,reason):
        await self.analysis.book_gap(symbols,reason)
        if self.on_gap:
            await self.on_gap(symbols,reason)

    async def start(self):
        if self.started:
            raise RuntimeError("session already running")
        await self.raw.start()
        try:
            await self.market.start(list(self.analysis.tapes))
        except BaseException:
            await self.raw.stop()
            raise
        self.started=True

    async def stop(self):
        await self.market.stop()
        await self.raw.stop()
        self.started=False
