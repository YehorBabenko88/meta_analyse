"""Thread-safe immutable GUI snapshots from async market analysis."""
from __future__ import annotations
from dataclasses import dataclass
from threading import Lock

@dataclass(frozen=True)
class FlowRow:
    symbol: str
    level: str
    poc: str
    delta: str
    tape_rate: str
    quality: str

class FlowBridge:
    def __init__(self):
        self._lock=Lock()
        self._rows={}

    async def update(self,symbol,footprint,tape):
        if tape is None:
            tape_rate="—"
            tape_ok=False
        else:
            tape_rate=str(tape.trades_per_second)
            tape_ok=tape.trusted
        row=FlowRow(symbol,"—",footprint.get("poc") or "—",
                    footprint.get("delta","—"),tape_rate,
                    "PROVISIONAL" if footprint.get("trusted") and tape_ok else "UNVERIFIED")
        with self._lock:
            self._rows[symbol]=row

    def snapshot(self):
        with self._lock:
            return tuple(self._rows[key] for key in sorted(self._rows))

    def invalidate(self,symbols):
        with self._lock:
            for symbol in symbols:
                old=self._rows.get(symbol)
                if old:
                    self._rows[symbol]=FlowRow(old.symbol,old.level,old.poc,old.delta,
                                               old.tape_rate,"UNVERIFIED")
