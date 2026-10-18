"""Read-only PostgreSQL adapter for historical trades consumed by Order Flow."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal


def read_orderflow_trades(store, *, venue: str, symbol: str,
                          start_ms: int, end_ms: int, limit: int = 10000):
    """Return timestamp_ms/volume aliases without mutating archive tables.

    Interval is [start_ms, end_ms); rows are ordered deterministically.
    Coverage/completeness is not implied by the returned records.
    """
    if not venue or not symbol:
        raise ValueError("venue and symbol are required")
    if type(start_ms) is not int or type(end_ms) is not int or start_ms < 0 or end_ms <= start_ms:
        raise ValueError("invalid timestamp interval")
    if type(limit) is not int or not 1 <= limit <= 100000:
        raise ValueError("invalid result limit")
    start = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    end = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)
    with store.connect() as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            rows = conn.execute("""SELECT trade_id,trade_ts,price,quantity,side
                FROM meta_analyse.historical_trades
                WHERE venue=%s AND symbol=%s AND trade_ts >= %s AND trade_ts < %s
                ORDER BY trade_ts,trade_id LIMIT %s""",
                (venue, symbol, start, end, limit)).fetchall()
    return [
        {
            "trade_id": trade_id,
            "timestamp_ms": int((trade_ts - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds() * 1000),
            "price": Decimal(price),
            "volume": Decimal(quantity),
            "side": side,
        }
        for trade_id, trade_ts, price, quantity, side in rows
    ]
