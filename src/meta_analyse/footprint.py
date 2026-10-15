"""Per-price bid/ask executed volume footprint, not resting orderbook liquidity."""
from __future__ import annotations
from dataclasses import dataclass,field
from decimal import Decimal
from .core import price_bucket

@dataclass
class FootprintCell:
    buy: Decimal=Decimal(0)
    sell: Decimal=Decimal(0)
    count: int=0

    @property
    def delta(self):
        return self.buy-self.sell

@dataclass
class Footprint:
    symbol: str
    start_ms: int
    interval_ms: int
    tick_size: Decimal
    cells: dict[Decimal,FootprintCell]=field(default_factory=dict)
    trusted: bool=True
    last_ts: int | None=None

    def add(self,event,*,contiguous):
        if event.symbol!=self.symbol or event.timestamp_ms<self.start_ms or event.timestamp_ms>=self.start_ms+self.interval_ms:
            raise ValueError("trade outside footprint")
        if self.last_ts is not None and event.timestamp_ms<self.last_ts:
            self.trusted=False
        if not contiguous:
            self.trusted=False
        self.last_ts=event.timestamp_ms
        price=price_bucket(event.price,self.tick_size)
        cell=self.cells.setdefault(price,FootprintCell())
        if event.taker_side=="Buy":
            cell.buy+=event.quantity
        elif event.taker_side=="Sell":
            cell.sell+=event.quantity
        else:
            raise ValueError("invalid taker side")
        cell.count+=1

    @property
    def poc(self):
        if not self.cells:
            return None
        return min(self.cells,key=lambda p:(-(self.cells[p].buy+self.cells[p].sell),p))

    @property
    def delta(self):
        return sum((c.delta for c in self.cells.values()),Decimal(0))

    def snapshot(self):
        return {"symbol":self.symbol,"start_ms":self.start_ms,
                "trusted":self.trusted,"poc":str(self.poc) if self.poc is not None else None,
                "delta":str(self.delta),
                "prices":{str(p):{"buy":str(c.buy),"sell":str(c.sell),
                                   "delta":str(c.delta),"trades":c.count}
                          for p,c in sorted(self.cells.items())}}
