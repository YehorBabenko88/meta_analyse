"""Evidence-based progress for bounded historical imports.

A percentage represents *verified coverage of a declared interval*, not bytes
downloaded or a promise of all-time exchange tick availability.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Availability(str, Enum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class Segment:
    start_ms: int
    end_ms: int
    source: str
    availability: Availability = Availability.UNKNOWN
    verified: bool = False
    records: int = 0

    def __post_init__(self):
        if self.start_ms >= self.end_ms:
            raise ValueError("segment interval must be nonempty")
        if self.records < 0:
            raise ValueError("negative record count")


@dataclass(frozen=True)
class Progress:
    percent: int | None
    status: str
    verified_ms: int
    required_ms: int


def coverage(segments: list[Segment], start_ms: int, end_ms: int) -> Progress:
    """Merge verified intervals; never double-count overlap or absent history."""
    if start_ms >= end_ms:
        raise ValueError("invalid requested interval")
    intervals = []
    blocked = False
    for segment in segments:
        left, right = max(start_ms, segment.start_ms), min(end_ms, segment.end_ms)
        if right <= left:
            continue
        if segment.availability in (Availability.UNAVAILABLE, Availability.UNSUPPORTED):
            blocked = True
        if segment.verified and segment.availability == Availability.AVAILABLE:
            intervals.append((left, right))
    intervals.sort()
    merged = []
    for left, right in intervals:
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    verified = sum(right - left for left, right in merged)
    total = end_ms - start_ms
    percent = verified * 100 // total
    if blocked:
        return Progress(percent if percent < 100 else 99, "source-limited", verified, total)
    return Progress(percent, "verified" if verified == total else "partial", verified, total)


def combined_readiness(streams: dict[str, Progress], required: tuple[str, ...] = ("candles", "trades", "ticks")) -> Progress:
    """Overall readiness cannot exceed the least-covered required feed.

    A missing stream is unknown, not 100%. A source-limited feed blocks
    readiness even if other streams have complete archives.
    """
    if not required:
        raise ValueError("at least one stream is required")
    missing = [kind for kind in required if kind not in streams]
    if missing:
        return Progress(None, "unknown: " + ", ".join(missing), 0, 0)
    parts = [streams[kind] for kind in required]
    if any(part.percent is None for part in parts):
        return Progress(None, "unknown", 0, 0)
    percent = min(part.percent for part in parts)
    limited = any(part.status == "source-limited" for part in parts)
    if limited:
        return Progress(min(percent, 99), "source-limited", 0, 0)
    return Progress(percent, "verified" if percent == 100 and all(p.status == "verified" for p in parts) else "partial", 0, 0)
