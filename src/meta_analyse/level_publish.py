"""Read-only safety checks before publishing price levels to a terminal."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from .level_quality import LevelReport

@dataclass(frozen=True)
class LevelPublication:
    allowed: bool
    reason: str
    count: int

def publication_decision(report: LevelReport, *, connection_verified: bool,
                         instrument_verified: bool, max_levels: int = 500) -> LevelPublication:
    if not connection_verified:
        return LevelPublication(False,"terminal connection not verified",0)
    if not instrument_verified:
        return LevelPublication(False,"instrument mapping not verified",0)
    if not report.verified:
        return LevelPublication(False,report.reason,0)
    if len(report.levels) > max_levels:
        return LevelPublication(False,"too many levels; explicit filtering required",0)
    if any(level.price <= Decimal(0) for level in report.levels):
        return LevelPublication(False,"invalid level price",0)
    return LevelPublication(True,"verified; publication may proceed with ownership checks",len(report.levels))
