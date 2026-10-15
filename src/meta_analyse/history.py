"""Explicit historical coverage scanner: do not claim completeness without evidence."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from decimal import Decimal
from .core import Candle

@dataclass(frozen=True)
class Coverage:
    expected: int
    received: int
    missing_starts: tuple[datetime, ...]
    complete: bool

def validate_fixed_interval(candles: list[Candle], start: datetime, end: datetime,
                            step: timedelta) -> Coverage:
    if start.tzinfo is None or end.tzinfo is None or step.total_seconds() <= 0:
        raise ValueError("UTC-aware bounds and positive interval required")
    observed = {c.start for c in candles}
    expected = 0
    missing = []
    cursor = start
    while cursor < end:
        expected += 1
        if cursor not in observed:
            missing.append(cursor)
        cursor += step
    return Coverage(expected, expected - len(missing), tuple(missing), not missing)

def yearly_from_daily(candles: list[Candle], now: datetime | None = None) -> list[Candle]:
    """Calendar UTC years only. Reject years with missing dates; no synthetic bars."""
    now = now or datetime.now(timezone.utc)
    groups: dict[int, list[Candle]] = {}
    for candle in candles:
        groups.setdefault(candle.start.year, []).append(candle)
    out = []
    for year, values in sorted(groups.items()):
        begin = datetime(year, 1, 1, tzinfo=timezone.utc)
        finish = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        if finish > now:
            continue
        coverage = validate_fixed_interval(values, begin, finish, timedelta(days=1))
        if not coverage.complete:
            continue
        ordered = sorted(values, key=lambda c: c.start)
        out.append(Candle(begin, max(c.high for c in ordered), min(c.low for c in ordered),
                          ordered[0].open, ordered[-1].close, sum((c.volume for c in ordered), Decimal(0))))
    return out

async def collect_history(exchange, store, symbol: str, timeframe: str,
                          listing_ms: int, end_ms: int) -> dict:
    """Backfill all API-returned pages; report bounds and gaps, never fabricate coverage."""
    count = 0
    first = None
    last = None
    async for page in exchange.candles(symbol, timeframe, listing_ms, end_ms):
        if not page:
            continue
        store.candle_batch(symbol, timeframe, page)
        count += len(page)
        low = min(c.start for c in page)
        high = max(c.start for c in page)
        first = low if first is None else min(first, low)
        last = high if last is None else max(last, high)
    return {"symbol": symbol, "timeframe": timeframe, "received": count,
            "earliest": first.isoformat() if first else None,
            "latest": last.isoformat() if last else None,
            "verified_complete": False,
            "reason": "API pagination alone does not prove no missing bars or earlier history"}
