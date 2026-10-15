"""Thread-safe immutable GUI snapshots from async market analysis."""
from __future__ import annotations
from dataclasses import dataclass
from threading import Lock
from .market_health import MarketHealthMonitor

@dataclass(frozen=True)
class FlowRow:
    symbol: str
    level: str
    poc: str
    delta: str
    tape_rate: str
    quality: str
    spread: str = "—"
    imbalance: str = "—"
    wall: str = "—"

class FlowBridge:
    def __init__(self):
        self._lock=Lock()
        self._rows={}
        self.health=MarketHealthMonitor()
        self._books={}

    async def update(self,symbol,footprint,tape):
        if tape is None:
            tape_rate="—"
            tape_ok=False
        else:
            tape_rate=str(tape.trades_per_second)
            tape_ok=tape.trusted
        row=FlowRow(symbol,"—",footprint.get("poc") or "—",
                    footprint.get("delta","—"),tape_rate,
                    "PROVISIONAL" if footprint.get("trusted") and tape_ok else "UNVERIFIED")
        with self._lock:
            self._rows[symbol]=row

    def trade_observed(self,symbol):
        self.health.execution(symbol)

    def book_observed(self,symbol,summary=None):
        self.health.book(symbol)
        if summary is not None:
            with self._lock:
                self._books[symbol]=summary

    def source_gap(self,source,symbols):
        self.health.gap(source,symbols)

    def snapshot(self):
        with self._lock:
            rows=tuple(self._rows[key] for key in sorted(self._rows))
            books=dict(self._books)
        health={entry.symbol:entry for entry in self.health.snapshot([r.symbol for r in rows])}
        result=[]
        for row in rows:
            status="UNVERIFIED" if row.quality=="UNVERIFIED" else health[row.symbol].combined
            book=books.get(row.symbol)
            if book is not None and book.valid and status=="PROVISIONAL":
                spread=str(book.spread_ticks)
                total=book.bid_notional+book.ask_notional
                imbalance=str(round((book.bid_notional-book.ask_notional)/total,4)) if total else "—"
                wall=(f"{book.largest_nearby[0].side} {book.largest_nearby[0].price}"
                      if book.largest_nearby else "—")
            else:
                spread=imbalance=wall="—"
            result.append(FlowRow(row.symbol,row.level,row.poc,row.delta,row.tape_rate,
                                  status,spread,imbalance,wall))
        return tuple(result)

    def invalidate(self,symbols):
        self.health.gap("trades",symbols)
        self.health.gap("orderbook",symbols)
        with self._lock:
            for symbol in symbols:
                self._books.pop(symbol,None)
                old=self._rows.get(symbol)
                if old:
                    self._rows[symbol]=FlowRow(old.symbol,old.level,old.poc,old.delta,
                                               old.tape_rate,"UNVERIFIED")
