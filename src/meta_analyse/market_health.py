"""Read-only market-data health aggregation; no GUI or network dependencies."""
from __future__ import annotations
from dataclasses import dataclass
from .feed_watchdog import FeedWatchdog

@dataclass(frozen=True)
class MarketHealth:
    symbol: str
    trades: str
    orderbook: str
    combined: str
    trades_age_s: float
    orderbook_age_s: float

class MarketHealthMonitor:
    def __init__(self, stale_after_seconds=8):
        self.trades=FeedWatchdog(stale_after_seconds)
        self.orderbook=FeedWatchdog(stale_after_seconds)

    def execution(self,symbol):
        self.trades.observed(symbol)

    def book(self,symbol):
        self.orderbook.observed(symbol)

    def gap(self,source,symbols):
        if source=="trades":
            self.trades.gap(symbols)
        elif source=="orderbook":
            self.orderbook.gap(symbols)
        else:
            raise ValueError("unknown source")

    def snapshot(self,symbols):
        trade={x.symbol:x for x in self.trades.inspect(symbols)}
        books={x.symbol:x for x in self.orderbook.inspect(symbols)}
        rows=[]
        for symbol in symbols:
            t,b=trade[symbol],books[symbol]
            if "UNVERIFIED" in (t.status,b.status):
                combined="UNVERIFIED"
            elif "STALE" in (t.status,b.status):
                combined="STALE"
            else:
                combined="PROVISIONAL"
            rows.append(MarketHealth(symbol,t.status,b.status,combined,t.age_seconds,b.age_seconds))
        return tuple(rows)
