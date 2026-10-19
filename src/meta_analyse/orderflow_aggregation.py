"""Pure aggregation of trades into time and tick-price buckets."""
from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR
from .orderflow_metrics import calculate


def _summarize(groups, initial_delta=Decimal(0)):
    cumulative = initial_delta
    rows = []
    for key in sorted(groups):
        metrics = calculate(groups[key], initial_delta=cumulative)
        cumulative = metrics.cumulative_delta
        rows.append((key, metrics))
    return tuple(rows)


def aggregate_by_time(trades, interval_ms, *, initial_delta=Decimal(0)):
    """Epoch-aligned, half-open buckets with time-ordered cumulative delta."""
    if not isinstance(interval_ms, int) or isinstance(interval_ms, bool) or interval_ms <= 0:
        raise ValueError("interval_ms must be a positive integer")
    groups = defaultdict(list)
    for trade in trades:
        if not isinstance(trade.timestamp_ms, int) or isinstance(trade.timestamp_ms, bool):
            raise ValueError("timestamp_ms must be an integer")
        groups[trade.timestamp_ms // interval_ms * interval_ms].append(trade)
    return _summarize(groups, initial_delta)


def aggregate_by_price(trades, tick_size, *, initial_delta=Decimal(0)):
    """Floor to tick price; cumulative delta runs in ascending price order."""
    if isinstance(tick_size, bool):
        raise ValueError("tick_size must be finite and positive")
    try:
        tick_size = Decimal(str(tick_size))
    except (ArithmeticError, ValueError) as exc:
        raise ValueError("tick_size must be finite and positive") from exc
    if not tick_size.is_finite() or tick_size <= 0:
        raise ValueError("tick_size must be finite and positive")
    groups = defaultdict(list)
    for trade in trades:
        if not trade.price.is_finite() or trade.price <= 0:
            raise ValueError("price must be finite and positive")
        index = (trade.price / tick_size).to_integral_value(rounding=ROUND_FLOOR)
        groups[index * tick_size].append(trade)
    return _summarize(groups, initial_delta)
