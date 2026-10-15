"""Bybit public orderbook stream with explicit gap invalidation."""
from __future__ import annotations
import asyncio
import json
import logging
import websockets
from .orderbook import OrderBook

LOG=logging.getLogger(__name__)

class OrderBookStream:
    def __init__(self,on_book,on_gap,*,depth=50,url="wss://stream.bybit.com/v5/public/linear"):
        if depth not in (1,50,200,500):
            raise ValueError("unsupported Bybit linear orderbook depth")
        self.on_book=on_book
        self.on_gap=on_gap
        self.depth=depth
        self.url=url
        self.books={}

    async def run(self,symbols,stop):
        if not symbols or len(symbols)>10:
            raise ValueError("use one book connection per 1..10 symbols")
        self.books={s:OrderBook(s) for s in symbols}
        delay=1
        while not stop.is_set():
            try:
                for book in self.books.values():
                    book.reset()
                await self.on_gap(symbols,"orderbook reconnect requires fresh snapshots")
                async with websockets.connect(self.url,ping_interval=20,ping_timeout=15,
                                              max_queue=1024,max_size=8_388_608) as ws:
                    await ws.send(json.dumps({"op":"subscribe","args":[
                        f"orderbook.{self.depth}.{s}" for s in symbols]}))
                    delay=1
                    while not stop.is_set():
                        try:
                            msg=json.loads(await asyncio.wait_for(ws.recv(),timeout=1))
                        except asyncio.TimeoutError:
                            continue
                        if msg.get("op")=="subscribe":
                            if msg.get("success") is False:
                                raise ConnectionError("orderbook subscription rejected")
                            continue
                        topic=str(msg.get("topic",""))
                        if not topic.startswith(f"orderbook.{self.depth}."):
                            continue
                        symbol=topic.rsplit(".",1)[-1]
                        book=self.books.get(symbol)
                        if book is None:
                            continue
                        try:
                            valid=book.apply(msg)
                        except (ValueError,KeyError,TypeError):
                            book.reset()
                            valid=False
                        if not valid:
                            await self.on_gap([symbol],"invalid orderbook snapshot or delta")
                            continue
                        await self.on_book(symbol,book,int(msg.get("ts",0)))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOG.warning("Orderbook reconnect: %s",exc)
                for book in self.books.values():
                    book.reset()
                await self.on_gap(symbols,"orderbook disconnected")
                await asyncio.sleep(delay)
                delay=min(delay*2,60)
