"""Pure time-bucket aggregation for read-only order flow."""
from collections import defaultdict
from .orderflow_metrics import calculate

def aggregate_by_time(trades, interval_ms):
    if interval_ms <= 0:
        raise ValueError('interval_ms must be positive')
    buckets = defaultdict(list)
    for trade in trades:
        buckets[trade.timestamp_ms // interval_ms * interval_ms].append(trade)
    return tuple((key, calculate(buckets[key])) for key in sorted(buckets))
