"""Collect orderbooks and open interest with isolated failure handling."""
from __future__ import annotations
import asyncio
import logging
from .market_store import MarketStore
from .orderbook_stream import OrderBookStream
from .open_interest import fetch_open_interest

LOG=logging.getLogger(__name__)

class MarketCollector:
    def __init__(self,store,exchange,on_book=None,on_gap=None,oi_interval="5min"):
        self.db=MarketStore(store)
        self.exchange=exchange
        self.on_book=on_book
        self.on_gap=on_gap
        self.oi_interval=oi_interval
        self.stop_event=asyncio.Event()
        self.tasks=[]

    async def _book(self,symbol,book,exchange_ms):
        await asyncio.to_thread(self.db.book,symbol,book,exchange_ms)
        if self.on_book:
            await self.on_book(symbol,book,exchange_ms)

    async def _gap(self,symbols,reason):
        if self.on_gap:
            await self.on_gap(symbols,reason)

    async def _oi_loop(self,symbols):
        while not self.stop_event.is_set():
            for symbol in symbols:
                if self.stop_event.is_set():
                    break
                try:
                    points=await fetch_open_interest(self.exchange,symbol,self.oi_interval)
                    for point in points:
                        await asyncio.to_thread(self.db.open_interest,point,self.oi_interval)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    LOG.exception("Open interest collection failed for %s",symbol)
            try:
                await asyncio.wait_for(self.stop_event.wait(),timeout=300)
            except asyncio.TimeoutError:
                pass

    async def start(self,symbols):
        if self.tasks:
            raise RuntimeError("collector already started")
        if not symbols:
            raise ValueError("no symbols")
        await asyncio.to_thread(self.db.initialize)
        self.stop_event.clear()
        for offset in range(0,len(symbols),10):
            stream=OrderBookStream(self._book,self._gap)
            self.tasks.append(asyncio.create_task(stream.run(symbols[offset:offset+10],self.stop_event)))
        self.tasks.append(asyncio.create_task(self._oi_loop(symbols)))
        return self.tasks

    async def stop(self):
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks,return_exceptions=True)
        self.tasks.clear()
