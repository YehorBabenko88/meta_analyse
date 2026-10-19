"""Read-only historical PostgreSQL trades for Flow History.

Never infer completeness from imported rows. All public values are immutable,
Decimal-preserving, and scoped to one instrument and a half-open UTC interval.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(frozen=True)
class HistoricalTrade:
    trade_id: str
    timestamp: datetime
    price: Decimal
    quantity: Decimal
    side: str


@dataclass(frozen=True)
class FlowHistorySnapshot:
    symbol: str
    start: datetime
    end: datetime
    trades: tuple[HistoricalTrade, ...]
    status: str = "UNVERIFIED"
    truncated: bool = False


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(timezone.utc)


def read_flow_history(store, *, symbol: str, start: datetime, end: datetime,
                      venue: str = "bybit", limit: int = 5000) -> FlowHistorySnapshot:
    """Fetch ordered trades. No floats, implicit instrument, or silent truncation."""
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("explicit symbol required")
    if not isinstance(venue, str) or not venue.strip():
        raise ValueError("explicit venue required")
    if type(limit) is not int or not 1 <= limit <= 100000:
        raise ValueError("limit must be between 1 and 100000")
    start, end = _utc(start), _utc(end)
    if start >= end:
        raise ValueError("start must precede end")
    with store.connect() as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            rows = conn.execute(
                """SELECT trade_id, trade_ts, price, quantity, side
                   FROM meta_analyse.historical_trades
                   WHERE venue=%s AND symbol=%s AND trade_ts >= %s AND trade_ts < %s
                   ORDER BY trade_ts, trade_id LIMIT %s""",
                (venue, symbol, start, end, limit + 1),
            ).fetchall()
    truncated = len(rows) > limit
    trades = tuple(
        HistoricalTrade(str(trade_id), _utc(timestamp),
                        price if isinstance(price, Decimal) else Decimal(str(price)),
                        quantity if isinstance(quantity, Decimal) else Decimal(str(quantity)),
                        side)
        for trade_id, timestamp, price, quantity, side in rows[:limit]
    )
    return FlowHistorySnapshot(symbol, start, end, trades, truncated=truncated)


def to_orderflow_records(snapshot: FlowHistorySnapshot) -> tuple[dict, ...]:
    """Bridge PostgreSQL history to the Order Flow adapter's record contract.

    Milliseconds are derived by integer timedelta arithmetic, never floating
    point. The source snapshot remains UNVERIFIED and is not modified.
    """
    if not isinstance(snapshot, FlowHistorySnapshot):
        raise TypeError("FlowHistorySnapshot required")
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    records = []
    for trade in snapshot.trades:
        if trade.side not in ('Buy', 'Sell'):
            raise ValueError('unsupported historical aggressor side')
        if not trade.price.is_finite() or trade.price <= 0:
            raise ValueError('invalid historical trade price')
        if not trade.quantity.is_finite() or trade.quantity < 0:
            raise ValueError('invalid historical trade quantity')
        delta = _utc(trade.timestamp) - epoch
        timestamp_ms = ((delta.days * 86400 + delta.seconds) * 1000
                        + delta.microseconds // 1000)
        records.append({
            "timestamp_ms": timestamp_ms,
            "price": trade.price,
            "volume": trade.quantity,
            "side": trade.side.lower(),
        })
    return tuple(records)
