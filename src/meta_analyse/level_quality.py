"""Auditable candle-level eligibility: no levels from unverified candle sequences."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from .core import Candle, Level, untouched_levels
from .history import validate_fixed_interval

FIXED_STEPS={"M1":timedelta(minutes=1),"H1":timedelta(hours=1),"D1":timedelta(days=1)}

@dataclass(frozen=True)
class LevelReport:
    levels: tuple[Level,...]
    verified: bool
    missing: int
    reason: str

def verified_levels(candles: list[Candle], timeframe: str, start, end) -> LevelReport:
    if timeframe not in FIXED_STEPS:
        return LevelReport((),False,0,"calendar intervals need explicit boundary validation")
    if not candles:
        return LevelReport((),False,0,"no historical candles")
    coverage=validate_fixed_interval(candles,start,end,FIXED_STEPS[timeframe])
    if not coverage.complete:
        return LevelReport((),False,len(coverage.missing_starts),"missing historical candles")
    eligible=[c for c in candles if start <= c.start < end]
    return LevelReport(tuple(untouched_levels(eligible,timeframe)),True,0,"verified requested range")
