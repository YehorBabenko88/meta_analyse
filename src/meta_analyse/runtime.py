"""Non-trading WebSocket ingestion and bounded dynamic watchlist."""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
import websockets
from .core import Trade, new_minute, floor_minute, PaperEngine, RollingFlow

LOG = logging.getLogger(__name__)

class Runtime:
    def __init__(self, metascalp, exchange, store=None, tick_size=D("0.00000001")):
        self.api = metascalp
        self.exchange = exchange
        self.store = store
        self.tick_size = tick_size
        self.paper = PaperEngine()
        self.minutes = {}
        self.flow = {}
        self.symbols = []
        self.connection_id = None
        self.quality = "metascalp_aggregated"
        self.running = False

    async def refresh_watchlist(self):
        self.symbols = await self.exchange.top_volatile(20)
        return self.symbols

    def receive(self, msg):
        if msg.get("Type", "").lower() != "trade_update":
            return []
        data = msg.get("Data") or {}
        symbol = data.get("ticker")
        if symbol not in self.symbols:
            return []
        outputs = []
        for raw in data.get("trades", []):
            try:
                ts = datetime.fromisoformat(raw["time"].replace("Z", "+00:00"))
                t = Trade(symbol, ts, D(str(raw["price"])), D(str(raw["size"])), str(raw["side"]),
                          D(str(raw.get("highPrice", raw["price"]))),
                          D(str(raw.get("lowPrice", raw["price"]))))
                if t.size <= 0 or t.price <= 0:
                    continue
            except (KeyError, ValueError, TypeError):
                continue
            current = self.minutes.get(symbol)
            slot = floor_minute(ts)
            if current and slot < current.start:
                LOG.warning("Out-of-order trade discarded %s", symbol)
                continue
            if current and slot > current.start:
                current.complete = (slot - current.start == timedelta(minutes=1))
                if self.store:
                    self.store.profile(symbol, current, self.quality if current.complete else "gap")
                self.paper.on_closed_minute(symbol, current)
                outputs.append(("closed_minute", symbol, current))
                current = None
            if current is None:
                current = new_minute(t, self.tick_size, complete=True)
                self.minutes[symbol] = current
            else:
                current.add(t)
            self.flow.setdefault(symbol, RollingFlow()).add(t)
            fill = self.paper.on_trade(t)
            if fill:
                if self.store:
                    self.store.paper_fill(fill)
                outputs.append(("paper_fill", symbol, fill))
        return outputs

    async def run(self):
        self.running = True
        delay = 1
        while self.running:
            try:
                await self.api.discover()
                connections = await self.api.connections()
                if isinstance(connections, dict):
                    connections = connections.get("connections", connections.get("data", []))
                eligible = [c for c in connections if str(c.get("exchange", "")).lower() == "bybit"
                            and c.get("state") == 2]
                if not eligible:
                    raise ConnectionError("Connect a Bybit account in MetaScalp first")
                self.connection_id = eligible[0]["id"]
                await self.refresh_watchlist()
                port = int(self.api.base.rsplit(":", 1)[1])
                async with websockets.connect(f"ws://127.0.0.1:{port}/", max_size=4_194_304) as socket:
                    for symbol in self.symbols:
                        await socket.send(json.dumps({"Type":"trade_subscribe", "Data":{
                            "connectionId":self.connection_id,"ticker":symbol,"zoomIndex":1}}))
                        await socket.send(json.dumps({"Type":"orderbook_subscribe", "Data":{
                            "connectionId":self.connection_id,"ticker":symbol,"fetchSnapshot":False,"depthLevels":50}}))
                    delay = 1
                    next_refresh = asyncio.get_running_loop().time() + 300
                    while self.running:
                        if asyncio.get_running_loop().time() > next_refresh:
                            new = await self.exchange.top_volatile(20)
                            old = set(self.symbols)
                            for symbol in old - set(new):
                                for typ in ("trade_unsubscribe", "orderbook_unsubscribe"):
                                    await socket.send(json.dumps({"Type":typ,"Data":{"connectionId":self.connection_id,"ticker":symbol}}))
                                self.paper.reference.pop(symbol, None)
                            for symbol in set(new) - old:
                                for typ in ("trade_subscribe", "orderbook_subscribe"):
                                    await socket.send(json.dumps({"Type":typ,"Data":{"connectionId":self.connection_id,"ticker":symbol,
                                                                                        "fetchSnapshot":False}}))
                            self.symbols = new
                            next_refresh = asyncio.get_running_loop().time() + 300
                        try:
                            raw = await asyncio.wait_for(socket.recv(), timeout=1)
                            self.receive(json.loads(raw))
                        except asyncio.TimeoutError:
                            continue
            except (ConnectionError, OSError, websockets.WebSocketException, ValueError) as exc:
                LOG.warning("Market stream reconnect: %s", exc)
            except Exception:
                LOG.exception("Market stream failure")
            if self.running:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    def stop(self):
        self.running = False
