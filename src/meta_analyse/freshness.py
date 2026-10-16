"""UI-only freshness categories for locally persisted market events.

These thresholds are operator hints, not exchange latency or proof of completeness.
"""
from __future__ import annotations
from math import isfinite

def freshness_state(age_seconds: float | None, *, delayed_after: float = 2.0, stale_after: float = 10.0) -> str:
    if not 0 <= delayed_after < stale_after:
        raise ValueError("freshness thresholds must be ordered and nonnegative")
    if age_seconds is None or not isfinite(age_seconds) or age_seconds < 0:
        return "UNKNOWN"
    if age_seconds < delayed_after:
        return "FRESH"
    if age_seconds < stale_after:
        return "DELAYED"
    return "STALE"

def freshness_for_feed(feed_key: str, age_seconds: float | None) -> str:
    """Source-aware age thresholds; age measures local persistence, not Bybit latency.

    Orderbooks are streamed, while open-interest is polled approximately every
    five minutes. Unknown sources use the conservative streaming defaults.
    """
    if feed_key.startswith("open_interest:"):
        return freshness_state(age_seconds, delayed_after=360.0, stale_after=600.0)
    return freshness_state(age_seconds)
