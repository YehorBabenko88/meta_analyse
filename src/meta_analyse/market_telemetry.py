"""Bounded, thread-safe market telemetry counters for UI diagnostics.

Counts describe observed callback traffic, not guaranteed exchange completeness.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from threading import Lock

@dataclass(frozen=True)
class TelemetrySnapshot:
    events: tuple[tuple[str,int], ...]
    gaps: tuple[tuple[str,int], ...]

class MarketTelemetry:
    def __init__(self):
        self._lock=Lock()
        self._events=Counter()
        self._gaps=Counter()

    def observe(self,source:str,symbol:str):
        if not source or not symbol:
            raise ValueError("source and symbol required")
        with self._lock:
            self._events[(source,symbol)]+=1

    def gap(self,source:str,symbol:str):
        if not source or not symbol:
            raise ValueError("source and symbol required")
        with self._lock:
            self._gaps[(source,symbol)]+=1

    def snapshot(self)->TelemetrySnapshot:
        with self._lock:
            return TelemetrySnapshot(tuple(sorted((f"{source}:{symbol}",count)
                for (source,symbol),count in self._events.items())),
                tuple(sorted((f"{source}:{symbol}",count)
                for (source,symbol),count in self._gaps.items())))
