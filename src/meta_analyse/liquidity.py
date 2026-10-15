"""Quality-gated large-liquidity observations near a selected level."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class LiquiditySignal:
    symbol: str
    price: Decimal
    side: str
    notional: Decimal
    distance_ticks: Decimal
    relative_to_median: Decimal
    trusted: bool

def large_levels(book,level_price,tick_size,*,min_notional=Decimal("100000"),
                 min_relative=Decimal("5"),max_distance_ticks=Decimal("50")):
    if not book.valid or tick_size<=0:
        return []
    entries=[(side,price,price*size) for side,levels in
             (("bid",book.bids),("ask",book.asks)) for price,size in levels.items()]
    values=sorted(amount for _,_,amount in entries if amount>0)
    if not values:
        return []
    midpoint=len(values)//2
    median=values[midpoint] if len(values)%2 else (values[midpoint-1]+values[midpoint])/2
    if median<=0:
        return []
    results=[]
    for side,price,amount in entries:
        distance=abs(price-level_price)/tick_size
        relative=amount/median
        if amount>=min_notional and relative>=min_relative and distance<=max_distance_ticks:
            results.append(LiquiditySignal(book.symbol,price,side,amount,distance,relative,True))
    return sorted(results,key=lambda x:(x.distance_ticks,-x.notional))
