"""Bybit public orderbook transport with fail-closed autonomous recovery."""
from __future__ import annotations
import asyncio
import json
import logging
import random
import time
import websockets
from .orderbook import OrderBook

LOG = logging.getLogger(__name__)


class _ResubscribeRequired(ConnectionError):
    pass


class OrderBookStream:
    def __init__(self, on_book, on_gap, *, depth=50,
                 url="wss://stream.bybit.com/v5/public/linear",
                 silence_timeout=90, backoff_base=1, backoff_max=60):
        if depth not in (1, 50, 200, 500):
            raise ValueError("unsupported Bybit linear orderbook depth")
        if silence_timeout <= 0 or backoff_base <= 0 or backoff_max < backoff_base:
            raise ValueError("invalid reconnect configuration")
        self.on_book = on_book
        self.on_gap = on_gap
        self.depth = depth
        self.url = url
        self.books = {}
        self.silence_timeout = silence_timeout
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.connection_epoch = 0

    async def run(self, symbols, stop):
        if not symbols or len(symbols) > 10:
            raise ValueError("use one book connection per 1..10 symbols")
        self.books = {s: OrderBook(s) for s in symbols}
        delay = self.backoff_base
        while not stop.is_set():
            try:
                self.connection_epoch += 1
                for book in self.books.values():
                    book.reset()
                await self.on_gap(symbols, "orderbook reconnect requires fresh snapshots")
                async with websockets.connect(
                    self.url, ping_interval=20, ping_timeout=15,
                    max_queue=1024, max_size=8_388_608, close_timeout=2
                ) as ws:
                    await ws.send(json.dumps({"op": "subscribe", "args": [
                        f"orderbook.{self.depth}.{s}" for s in symbols]}))
                    # Each symbol must receive a fresh snapshot in this epoch.
                    last_message = {s: time.monotonic() for s in symbols}
                    while not stop.is_set():
                        if any(time.monotonic() - t >= self.silence_timeout
                               for t in last_message.values()):
                            raise _ResubscribeRequired("connected orderbook feed silent")
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=min(1, self.silence_timeout))
                        except asyncio.TimeoutError:
                            if any(time.monotonic() - t >= self.silence_timeout
                                   for t in last_message.values()):
                                raise _ResubscribeRequired("connected orderbook feed silent")
                            continue
                        try:
                            msg = json.loads(raw)
                        except (ValueError, TypeError) as exc:
                            raise _ResubscribeRequired("malformed orderbook JSON") from exc
                        if not isinstance(msg, dict):
                            raise _ResubscribeRequired("malformed orderbook envelope")
                        if msg.get("op") == "subscribe":
                            if msg.get("success") is False:
                                raise _ResubscribeRequired("orderbook subscription rejected")
                            continue
                        topic = msg.get("topic")
                        if not isinstance(topic, str) or not topic.startswith(f"orderbook.{self.depth}."):
                            continue
                        symbol = topic.rsplit(".", 1)[-1]
                        book = self.books.get(symbol)
                        if book is None:
                            continue
                        last_message[symbol] = time.monotonic()
                        try:
                            valid = book.apply(msg)
                        except (ValueError, KeyError, TypeError, ArithmeticError):
                            book.reset()
                            valid = False
                        if not valid:
                            await self.on_gap([symbol], "invalid orderbook snapshot or delta")
                            # Never accept a later delta in this connection/epoch.
                            raise _ResubscribeRequired("invalid orderbook; fresh snapshot required")
                        await self.on_book(symbol, book, int(msg.get("ts", 0)))
                        # Reset backoff only after a verified snapshot, not merely
                        # after a TCP/WebSocket handshake (which may flap rapidly).
                        if msg.get("type") == "snapshot":
                            delay = self.backoff_base
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOG.warning("Orderbook reconnect epoch=%d: %s", self.connection_epoch, exc)
                for book in self.books.values():
                    book.reset()
                await self.on_gap(symbols, "orderbook disconnected; data UNVERIFIED")
                if stop.is_set():
                    break
                # Bounded exponential backoff with jitter; stop remains interruptible.
                try:
                    await asyncio.wait_for(stop.wait(), timeout=min(
                        self.backoff_max, delay * random.uniform(0.8, 1.2)))
                except asyncio.TimeoutError:
                    pass
                delay = min(delay * 2, self.backoff_max)
