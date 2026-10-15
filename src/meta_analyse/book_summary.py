"""Bounded best-bid/ask and nearby liquidity summaries for a trader UI."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from .liquidity import large_levels

@dataclass(frozen=True)
class BookSummary:
    symbol: str
    best_bid: Decimal | None
    best_ask: Decimal | None
    spread_ticks: Decimal | None
    bid_notional: Decimal
    ask_notional: Decimal
    largest_nearby: tuple
    valid: bool

def summarize_book(book,tick_size,level_price=None,*,max_walls=3):
    if tick_size<=0 or max_walls<0:
        raise ValueError("invalid book summary settings")
    if not book.valid or not book.bids or not book.asks:
        return BookSummary(book.symbol,None,None,None,Decimal(0),Decimal(0),(),False)
    bid=max(book.bids)
    ask=min(book.asks)
    if bid>=ask:
        return BookSummary(book.symbol,None,None,None,Decimal(0),Decimal(0),(),False)
    bid_notional=sum((p*q for p,q in book.bids.items()),Decimal(0))
    ask_notional=sum((p*q for p,q in book.asks.items()),Decimal(0))
    walls=large_levels(book,level_price,tick_size) if level_price is not None else []
    return BookSummary(book.symbol,bid,ask,(ask-bid)/tick_size,bid_notional,
                       ask_notional,tuple(walls[:max_walls]),True)
