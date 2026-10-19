"""Read-only Bybit open interest history collector."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class OIPoint:
    symbol: str
    timestamp_ms: int
    open_interest: Decimal

def parse_oi(symbol,rows):
    points=[]
    for row in rows:
        ts=int(row["timestamp"])
        value=Decimal(str(row["openInterest"]))
        if ts<=0 or value<0:
            raise ValueError("invalid open interest sample")
        points.append(OIPoint(symbol,ts,value))
    return sorted(points,key=lambda x:x.timestamp_ms)

async def fetch_open_interest(exchange,symbol,interval="5min",start_ms=None,end_ms=None):
    if interval not in {"5min","15min","30min","1h","4h","1d"}:
        raise ValueError("unsupported Bybit OI interval")
    params={"category":"linear","symbol":symbol,"intervalTime":interval,"limit":200}
    if start_ms is not None:params["startTime"]=start_ms
    if end_ms is not None:params["endTime"]=end_ms
    result=await exchange.get("/v5/market/open-interest",params)
    return parse_oi(symbol,result.get("list",[]))
