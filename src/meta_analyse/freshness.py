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
