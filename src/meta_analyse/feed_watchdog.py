"""Bounded, thread-safe GUI market telemetry with stale-data detection."""
from __future__ import annotations
from dataclasses import dataclass
from threading import Lock
from time import monotonic

@dataclass(frozen=True)
class Telemetry:
    symbol: str
    age_seconds: float
    status: str

class FeedWatchdog:
    def __init__(self, stale_after_seconds: float = 8.0):
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        self.stale_after_seconds = stale_after_seconds
        self._lock = Lock()
        self._last: dict[str, float] = {}
        self._invalid: set[str] = set()

    def observed(self, symbol: str):
        with self._lock:
            self._last[symbol] = monotonic()
            self._invalid.discard(symbol)

    def gap(self, symbols):
        with self._lock:
            self._invalid.update(symbols)

    def inspect(self, symbols):
        now = monotonic()
        with self._lock:
            return tuple(Telemetry(symbol, max(0.0, now - self._last[symbol])
                                   if symbol in self._last else float("inf"),
                                   "UNVERIFIED" if symbol in self._invalid or symbol not in self._last
                                   else ("STALE" if now - self._last[symbol] > self.stale_after_seconds
                                         else "PROVISIONAL"))
                         for symbol in symbols)
