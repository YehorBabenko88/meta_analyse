"""Offline-wirable Bybit ingestion and analysis; no terminal writes or exchange orders."""
from __future__ import annotations
import asyncio
from .pipeline import RawPipeline
from .market_collector import MarketCollector
from .analysis_coordinator import AnalysisCoordinator

class AnalysisSession:
    def __init__(self,store,exchange,tick_sizes,*,on_update=None,on_gap=None):
        if not tick_sizes or any(not tick.is_finite() or tick <= 0 for tick in tick_sizes.values()):
            raise ValueError("tick sizes must be finite and positive")
        self._lifecycle_lock = asyncio.Lock()
        self._startup = None
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
        async with self._lifecycle_lock:
            if self.started:
                raise RuntimeError("session already running")
            self._startup = asyncio.current_task()
            try:
                await self.raw.start()
                await self.market.start(list(self.analysis.tapes))
                self.started = True
            except BaseException:
                # Both collectors may have allocated resources before failing.
                await self._cleanup()
                raise
            finally:
                self._startup = None

    async def _cleanup(self):
        self.started = False
        results = await asyncio.gather(self.market.stop(), self.raw.stop(), return_exceptions=True)
        symbols = list(self.analysis.tapes)
        await self.analysis.gap(symbols, "session stopped")
        await self.analysis.book_gap(symbols, "session stopped")
        if self.on_gap:
            await self.on_gap(symbols, "session stopped")
        for result in results:
            if isinstance(result, BaseException):
                raise result

    async def stop(self):
        startup = self._startup
        if startup is not None and startup is not asyncio.current_task():
            startup.cancel()
            await asyncio.gather(startup, return_exceptions=True)
        async with self._lifecycle_lock:
            await self._cleanup()
