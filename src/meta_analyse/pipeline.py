"""Durable raw Bybit ingestion pipeline; no inferred or synthetic trades."""
from __future__ import annotations
import asyncio
import logging
from decimal import Decimal
from .raw_trades import RawTradeStream
from .raw_store import RawStore
from .integrity import ExecutionAggregator
from .health import HealthTracker

LOG = logging.getLogger(__name__)

class RawPipeline:
    def __init__(self, store, tick_sizes: dict[str, Decimal], on_closed=None):
        self.db = RawStore(store)
        self.aggregators = {s: ExecutionAggregator(tick) for s, tick in tick_sizes.items()}
        self.on_closed = on_closed
        self.health = HealthTracker()
        self.stop_event = asyncio.Event()
        self.streams = []
        self.tasks = []

    async def execution(self, event):
        aggregator = self.aggregators.get(event.symbol)
        if aggregator is None:
            raise ValueError("unknown symbol or tick size")
        # Persist first. Only a durable, newly inserted execution enters calculations.
        inserted = await asyncio.to_thread(self.db.save, event)
        if not inserted:
            return
        self.health.record(event)
        before = len(aggregator.closed)
        aggregator.accept(event)
        for symbol, minute, quality in aggregator.closed[before:]:
            if quality != "observed_contiguous":
                continue
            if self.on_closed:
                await self.on_closed(symbol, minute, quality)

    async def gap(self, symbols, reason):
        # Fail closed if DB is unavailable; never report continuity.
        await asyncio.to_thread(self.db.gap, symbols, reason)
        for symbol in symbols:
            self.health.gap(symbol)
            if symbol in self.aggregators:
                self.aggregators[symbol].gap([symbol], reason)

    async def start(self):
        await asyncio.to_thread(self.db.initialize)
        symbols = list(self.aggregators)
        if not symbols:
            raise ValueError("no instruments")
        self.stop_event.clear()
        for offset in range(0, len(symbols), 10):
            stream = RawTradeStream(self.execution, self.gap)
            self.streams.append(stream)
            self.tasks.append(asyncio.create_task(stream.run(symbols[offset:offset+10], self.stop_event)))
        return self.tasks

    async def stop(self):
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.streams.clear()
