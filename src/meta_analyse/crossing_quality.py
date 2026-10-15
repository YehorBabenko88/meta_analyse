"""Never confuse a price jump across a data gap with a verified level crossing."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class CrossingObservation:
    previous: Decimal
    current: Decimal
    contiguous: bool
    source: str

def crossed_prices(observation: CrossingObservation, level: Decimal) -> bool:
    if not observation.contiguous:
        return False
    if observation.source != "exchange_execution":
        return False
    if observation.previous <= 0 or observation.current <= 0 or level <= 0:
        return False
    return min(observation.previous,observation.current) <= level <= max(observation.previous,observation.current)
