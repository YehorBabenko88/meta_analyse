"""Meta public DTO adapters for Math-owned time/price orderflow aggregation.

No independent aggregation implementation; historical callers retain FlowMetrics DTO.
"""
from decimal import Decimal
from market_profile_math import aggregate_orderflow
from .orderflow_metrics import FlowMetrics


def _adapt(trades, *, mode, interval_ms=None, tick_size=None, initial_delta=Decimal(0)):
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
