"""Meta public DTO adapters for Math-owned time/price orderflow aggregation.

No independent aggregation implementation; historical callers retain FlowMetrics DTO.
"""
from decimal import Decimal
from market_profile_math import aggregate_orderflow
from .orderflow_metrics import FlowMetrics


def _adapt(trades, *, mode, interval_ms=None, tick_size=None, initial_delta=Decimal(0)):
    # Legacy public API accepted numeric/string ticks; normalize only the DTO.
    # Bucket arithmetic, ordering and cumulative statistics remain Math-owned.
    if mode == "price":
        if isinstance(tick_size, bool):
            raise ValueError("tick_size must be finite and positive")
        try:
            tick_size = Decimal(str(tick_size))
        except (ArithmeticError, ValueError) as exc:
            raise ValueError("tick_size must be finite and positive") from exc
        if not tick_size.is_finite() or tick_size <= 0:
            raise ValueError("tick_size must be finite and positive")
    rows=[(trade.timestamp_ms,trade.price,trade.volume,trade.side) for trade in trades]
    grouped=aggregate_orderflow(rows,mode=mode,interval_ms=interval_ms,
                               tick_size=tick_size,initial_delta=initial_delta)
    return tuple((bucket,FlowMetrics(
        result["buy_volume"],result["sell_volume"],result["unknown_volume"],
        result["delta"],result["cumulative_delta"],result["imbalance"],
        result["trade_count"])) for bucket,result in grouped)


def aggregate_by_time(trades, interval_ms, *, initial_delta=Decimal(0)):
    return _adapt(trades,mode="time",interval_ms=interval_ms,initial_delta=initial_delta)


def aggregate_by_price(trades, tick_size, *, initial_delta=Decimal(0)):
    return _adapt(trades,mode="price",tick_size=tick_size,initial_delta=initial_delta)
