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
        if not tick_sizes or any(not tick.is_finite() or tick <= 0 for tick in tick_sizes.values()):
            raise ValueError("tick sizes must be finite and positive")
        self._lifecycle_lock = asyncio.Lock()
        self._startup = None
        self._stop_task = None
        self._needs_cleanup = False
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
        # Reject queued starts: otherwise a waiting start can acquire the lock
        # between cancellation of the first startup and stop() cleanup.
        if (self._lifecycle_lock.locked()
                or self._stop_task is not None and not self._stop_task.done()):
            raise RuntimeError("session lifecycle operation already in progress")
        async with self._lifecycle_lock:
            if self.started:
                raise RuntimeError("session already running")
            self._startup = asyncio.current_task()
            self._needs_cleanup = True
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
        # Sessions reconstructed by health monitoring may already own collector
        # tasks even when start() was not called on this instance.
        if (not self._needs_cleanup and not self.started
                and not self.raw.tasks and not self.market.tasks):
            return
        self._needs_cleanup = False
        self.started = False
        results = await asyncio.gather(self.market.stop(), self.raw.stop(), return_exceptions=True)
        symbols = list(self.analysis.tapes)
        await self.analysis.gap(symbols, "session stopped")
        await self.analysis.book_gap(symbols, "session stopped")
        self.health.gap("trades", symbols)
        self.health.gap("orderbook", symbols)
        if self.on_gap:
            await self.on_gap(symbols, "session stopped")
        for result in results:
            if isinstance(result, BaseException):
                raise result

    async def stop(self):
        # Claim stop ownership before yielding; completion callbacks must not
        # restart collectors between startup cancellation and cleanup.
        if self._stop_task is None or self._stop_task.done():
            self._stop_task = asyncio.create_task(self._stop())
        await asyncio.shield(self._stop_task)

    async def _stop(self):
        startup = self._startup
        if startup is not None and startup is not asyncio.current_task():
            startup.cancel()
            await asyncio.gather(startup, return_exceptions=True)
        async with self._lifecycle_lock:
            await self._cleanup()
