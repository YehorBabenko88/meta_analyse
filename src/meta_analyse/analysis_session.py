"""Offline-wirable Bybit ingestion and analysis; no terminal writes or exchange orders."""
from __future__ import annotations
import asyncio
from .pipeline import RawPipeline
from .market_collector import MarketCollector
from .analysis_coordinator import AnalysisCoordinator
from .market_health import MarketHealthMonitor
from .book_summary import summarize_book

class AnalysisSession:
    def __init__(self,store,exchange,tick_sizes,*,on_update=None,on_gap=None,on_book_update=None):
        self.analysis=AnalysisCoordinator(tick_sizes)
        self.health=MarketHealthMonitor()
        self.on_update=on_update
        self.on_gap=on_gap
        self.on_book_update=on_book_update
        self.raw=RawPipeline(store,tick_sizes,
                             on_execution=self._execution,on_gap=self._trade_gap)
        self.market=MarketCollector(store,exchange,
                                    on_book=self._book,on_gap=self._book_gap)
        self.started=False

    def select_level(self,symbol,price):
        self.analysis.set_level(symbol,price)

    async def _execution(self,event,*,contiguous):
        footprint,tape=await self.analysis.execution(event,contiguous=contiguous)
        if contiguous:
            self.health.execution(event.symbol)
        else:
            self.health.gap("trades",[event.symbol])
        if self.on_update and footprint is not None:
            await self.on_update(event.symbol,footprint.snapshot(),tape)

    async def _trade_gap(self,symbols,reason):
        await self.analysis.gap(symbols,reason)
        self.health.gap("trades",symbols)
        if self.on_gap:
            await self.on_gap(symbols,reason)

    async def _book(self,symbol,book,timestamp_ms):
        await self.analysis.book(symbol,book,timestamp_ms)
        if book.valid:
            self.health.book(symbol)
            if self.on_book_update:
                level=self.analysis.levels.get(symbol)
                summary=summarize_book(book,self.analysis.footprints.tick_sizes[symbol],level)
                await self.on_book_update(symbol,summary)
        else:
            self.health.gap("orderbook",[symbol])

    async def _book_gap(self,symbols,reason):
        await self.analysis.book_gap(symbols,reason)
        self.health.gap("orderbook",symbols)
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
