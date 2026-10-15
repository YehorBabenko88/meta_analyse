"""MetaScalp localhost REST client. No sockets are bound by this application."""
from __future__ import annotations
import httpx
import asyncio

class MetaScalp:
    def __init__(self):
        self.base: str | None = None
        self.client = httpx.AsyncClient(timeout=3, trust_env=False)

    async def discover(self) -> str:
        for port in range(17845, 17856):
            root = f"http://127.0.0.1:{port}"
            try:
                resp = await self.client.get(root + "/ping")
                if resp.is_success:
                    data = resp.json()
                    if isinstance(data, dict) and "meta" in str(data).lower():
                        self.base = root
                        return root
            except (httpx.HTTPError, ValueError):
                continue
        raise ConnectionError("MetaScalp not found on localhost ports 17845..17855")

    async def request(self, method: str, endpoint: str, **kwargs):
        if not self.base:
            await self.discover()
        # Retry reads only: a timed-out POST/DELETE may already have executed.
        attempts = 3 if method.upper() == "GET" else 1
        for attempt in range(attempts):
            try:
                resp = await self.client.request(method, self.base + endpoint, **kwargs)
                resp.raise_for_status()
                return resp.json() if resp.content else None
            except (httpx.TransportError, httpx.HTTPStatusError):
                if attempt == attempts - 1:
                    self.base = None
                    raise
                await asyncio.sleep(0.25 * (2 ** attempt))

    async def connections(self):
        return await self.request("GET", "/api/connections")

    async def open_combos(self, symbols: list[str]):
        if not symbols or len(symbols) > 20:
            raise ValueError("Select 1 to 20 tickers")
        return await self.request("POST", "/api/combo", json={"tickers": symbols, "activate": True})

    async def levels(self, connection: int, ticker: str):
        return await self.request("GET", f"/api/connections/{connection}/signal-levels", params={"Ticker": ticker})

    async def add_level(self, connection: int, ticker: str, price: str, rule: str, note: str):
        if rule not in ("LessThanEqual", "GreaterThanEqual"):
            raise ValueError("bad trigger rule")
        return await self.request("POST", f"/api/connections/{connection}/signal-levels", json={
            "ticker": ticker, "price": price, "triggerRule": rule, "note": note,
            "lineStyle": "Dashed", "lineThickness": 1, "lineColor": "#E0AA44"})

    async def remove_level(self, connection: int, level_id: int):
        return await self.request("DELETE", f"/api/connections/{connection}/signal-levels/{level_id}")

    async def close(self):
        await self.client.aclose()
