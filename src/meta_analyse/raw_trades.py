"""Loss-aware Bybit V5 raw trade stream. Never manufacture missing ticks."""
from __future__ import annotations
import asyncio
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
import websockets

LOG = logging.getLogger(__name__)

@dataclass(frozen=True)
class RawExecution:
    symbol: str
    execution_id: str
    timestamp_ms: int
    price: Decimal
    quantity: Decimal
    taker_side: str

def parse_public_trade(message: dict) -> list[RawExecution]:
    if not str(message.get("topic", "")).startswith("publicTrade."):
        return []
    result = []
    for row in message.get("data", []):
        try:
            item = RawExecution(
                symbol=str(row["s"]), execution_id=str(row["i"]),
                timestamp_ms=int(row["T"]), price=Decimal(str(row["p"])),
                quantity=Decimal(str(row["v"])), taker_side=str(row["S"]))
            if (item.price <= 0 or item.quantity <= 0 or
                item.taker_side not in ("Buy", "Sell") or not item.execution_id):
                raise ValueError("invalid execution")
            result.append(item)
        except (KeyError, ValueError, ArithmeticError) as exc:
            raise ValueError(f"Malformed publicTrade: {exc}") from exc
    return result

class RawTradeStream:
    """One exchange WS per <=10 symbols; callback must durably commit before returning."""
    def __init__(self, on_execution, on_gap, url="wss://stream.bybit.com/v5/public/linear"):
        self.on_execution = on_execution
        self.on_gap = on_gap
        self.url = url
        self.seen = set()
        self.seen_order = []
        self.max_seen = 200000

    async def run(self, symbols: list[str], stop: asyncio.Event):
        if not symbols or len(symbols) > 10:
            raise ValueError("Use one stream per 1..10 symbols")
        delay = 1
        while not stop.is_set():
            try:
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=15,
                                              max_queue=1024, max_size=8_388_608) as ws:
                    await ws.send(json.dumps({"op": "subscribe", "args": [
                        f"publicTrade.{symbol}" for symbol in symbols]}))
                    await self.on_gap(symbols, "connect_or_reconnect: historical tick continuity unverified")
                    delay = 1
                    while not stop.is_set():
                        try:
                            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=1))
                        except asyncio.TimeoutError:
                            continue
                        if msg.get("op") == "subscribe":
                            if msg.get("success") is False:
                                raise ConnectionError(f"Subscription rejected: {msg}")
                            continue
                        for execution in parse_public_trade(msg):
                            key = (execution.symbol, execution.execution_id)
                            if key in self.seen:
                                continue
                            # Commit before marking seen: never silently drop a failed DB write.
                            await self.on_execution(execution)
                            self.seen.add(key)
                            self.seen_order.append(key)
                            if len(self.seen_order) > self.max_seen:
                                self.seen.discard(self.seen_order.pop(0))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOG.warning("Bybit raw trade stream disconnected: %s", exc)
                await self.on_gap(symbols, str(exc))
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
