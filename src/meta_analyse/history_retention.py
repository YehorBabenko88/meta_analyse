"""Conservative retention planner for large historical trade datasets.

No filesystem deletion occurs here. An explicit manifest marks which source
files have durable derived features and which are protected for reproducibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class RetentionRecord:
    path: str
    bytes: int
    created_at: datetime
    derived_committed: bool
    source_recoverable: bool
    protected: bool = False
    active: bool = False


@dataclass(frozen=True)
class RetentionDecision:
    path: str
    eligible: bool
    reason: str
    bytes_reclaimable: int


def plan_retention(records: list[RetentionRecord], *,
                   now: datetime | None = None,
                   min_age_days: int = 90) -> list[RetentionDecision]:
    if min_age_days < 1:
        raise ValueError("minimum age must be positive")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    cutoff = now - timedelta(days=min_age_days)
    result = []
    for item in records:
        if not item.path or item.bytes < 0 or item.created_at.tzinfo is None:
            raise ValueError("invalid retention manifest record")
        if item.protected:
            reason = "protected for reproducibility"
        elif item.active:
            reason = "active analysis or download"
        elif item.created_at > cutoff:
            reason = "inside minimum retention window"
        elif not item.derived_committed:
            reason = "derived analysis not durably committed"
        elif not item.source_recoverable:
            reason = "source cannot be reconstructed"
        else:
            reason = "eligible for manual review"
        eligible = reason == "eligible for manual review"
        result.append(RetentionDecision(item.path, eligible, reason,
                                        item.bytes if eligible else 0))
    return result
