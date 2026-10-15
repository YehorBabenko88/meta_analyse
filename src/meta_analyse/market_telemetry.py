"""Thread-safe market telemetry counters and monotonic freshness tracking.

Counts describe observed callback traffic, not guaranteed exchange completeness.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from threading import Lock
from time import monotonic

@dataclass(frozen=True)
class TelemetrySnapshot:
    events: tuple[tuple[str,int], ...]
    gaps: tuple[tuple[str,int], ...]

class MarketTelemetry:
    def __init__(self):
        self._lock=Lock()
        self._events=Counter()
        self._gaps=Counter()
        self._last_seen={}

    def observe(self,source:str,symbol:str):
        if not source or not symbol:
            raise ValueError("source and symbol required")
        with self._lock:
            self._events[(source,symbol)]+=1
            self._last_seen[(source,symbol)]=monotonic()

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

    def ages(self, now=None)->tuple[tuple[str,float], ...]:
        """Seconds since locally observed successful persistence; not exchange latency."""
        current=monotonic() if now is None else now
        with self._lock:
            return tuple(sorted((f"{source}:{symbol}",max(0.0,current-seen))
                for (source,symbol),seen in self._last_seen.items()))
