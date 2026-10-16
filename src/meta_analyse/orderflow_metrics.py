"""Pure, deterministic trade-side volume metrics (no network, database or orders)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True)
class Trade:
    timestamp_ms: int
    price: Decimal
    volume: Decimal
    side: str  # buy, sell, or unknown


@dataclass(frozen=True)
class FlowMetrics:
    buy_volume: Decimal
    sell_volume: Decimal
    unknown_volume: Decimal
    delta: Decimal
    cumulative_delta: Decimal
    imbalance: Decimal | None
    trade_count: int


def calculate(trades: Iterable[Trade], *, initial_delta: Decimal = Decimal(0)) -> FlowMetrics:
    """Imbalance=(buy-sell)/(buy+sell); None when no classified volume exists."""
    buy = sell = unknown = Decimal(0)
    count = 0
    for trade in trades:
        if not trade.price.is_finite() or trade.price <= 0:
            raise ValueError("trade price must be finite and positive")
        if not trade.volume.is_finite() or trade.volume < 0:
            raise ValueError("trade volume must be finite and nonnegative")
        if trade.side == "buy":
            buy += trade.volume
        elif trade.side == "sell":
            sell += trade.volume
        elif trade.side == "unknown":
            unknown += trade.volume
        else:
            raise ValueError("unsupported trade side")
        count += 1
    delta = buy - sell
    classified = buy + sell
    return FlowMetrics(
        buy, sell, unknown, delta, initial_delta + delta,
        delta / classified if classified else None, count,
    )
