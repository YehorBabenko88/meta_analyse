"""Quality-gated large-liquidity observations near a selected level."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from market_profile_math import large_liquidity_levels

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
    results = large_liquidity_levels(
        book.bids, book.asks, level_price, tick_size,
        min_notional=min_notional, min_relative=min_relative,
        max_distance_ticks=max_distance_ticks)
    return [LiquiditySignal(book.symbol,price,side,amount,distance,relative,True)
            for side,price,amount,distance,relative in results]
