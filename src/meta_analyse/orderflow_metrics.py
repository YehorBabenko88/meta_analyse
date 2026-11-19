"""Pure, deterministic trade-side volume metrics (no network, database or orders)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from market_profile_math import orderflow_volume_metrics


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
    if not isinstance(initial_delta, Decimal) or not initial_delta.is_finite():
        raise ValueError("initial_delta must be a finite Decimal")
    records = [(trade.price, trade.volume, trade.side) for trade in trades]
    metrics = orderflow_volume_metrics(records, initial_delta)
    return FlowMetrics(
        metrics["buy_volume"], metrics["sell_volume"], metrics["unknown_volume"],
        metrics["delta"], metrics["cumulative_delta"], metrics["imbalance"],
        metrics["trade_count"]
    )
