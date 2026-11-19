"""Legacy Order Flow archive API over the one read-only historical-trade reader.

This preserves the existing output shape while removing a second, divergent
SQL query path. Neither this view nor the underlying snapshot proves that
archive history is complete or exchange-authentic.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from .flow_history_storage import read_flow_history


def read_orderflow_trades(store, *, venue: str, symbol: str,
                          start_ms: int, end_ms: int, limit: int = 10000):
    """Return legacy trade records over the canonical bounded read-only query.

    Interval is [start_ms, end_ms); results preserve Decimal precision.
    The result may be limited and does not establish source completeness.
    """
    if not venue or not symbol:
        raise ValueError("venue and symbol are required")
    if type(start_ms) is not int or type(end_ms) is not int or start_ms < 0 or end_ms <= start_ms:
        raise ValueError("invalid timestamp interval")
    if type(limit) is not int or not 1 <= limit <= 100000:
        raise ValueError("invalid result limit")
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    start = epoch + timedelta(milliseconds=start_ms)
    end = epoch + timedelta(milliseconds=end_ms)
    snapshot = read_flow_history(
        store, venue=venue, symbol=symbol, start=start, end=end, limit=limit
    )
    # Preserve the old archive-record shape, including historically unknown sides.
    # No publication/readiness flag is added; Grid remains the future owner.
    records = []
    for trade in snapshot.trades:
        delta = trade.timestamp - epoch
        records.append({
            "trade_id": trade.trade_id,
            "timestamp_ms": (
                (delta.days * 86400 + delta.seconds) * 1000
                + delta.microseconds // 1000
            ),
            "price": trade.price,
            "volume": trade.quantity,
            "side": trade.side,
        })
    return records
