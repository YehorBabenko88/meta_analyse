"""Crash-safe, bounded historical coverage checkpoints.

Only independently verified intervals are persisted as complete. Writes are
atomic; interrupted imports remain pending and must be revalidated.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile

from .history_progress import Availability, Segment, coverage


@dataclass(frozen=True)
class HistoryKey:
    symbol: str
    kind: str
    start_ms: int
    end_ms: int

    def __post_init__(self):
        if not self.symbol or not self.kind or self.start_ms >= self.end_ms:
            raise ValueError("invalid history key")


class HistoryCheckpoint:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self, key: HistoryKey) -> list[Segment]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or payload.get("key") != asdict(key):
            return []
        return [Segment(int(x["start_ms"]), int(x["end_ms"]), str(x["source"]),
                        Availability(x["availability"]), bool(x["verified"]),
                        int(x["records"])) for x in payload["segments"]]

    def save(self, key: HistoryKey, segments: list[Segment]):
        for segment in segments:
            if segment.start_ms < key.start_ms or segment.end_ms > key.end_ms:
                raise ValueError("segment outside requested interval")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "key": asdict(key), "segments": [
            {**asdict(x), "availability": x.availability.value} for x in segments]}
        temp = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8",
                                             dir=self.path.parent, delete=False) as handle:
                temp = Path(handle.name)
                json.dump(data, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    def progress(self, key: HistoryKey):
        return coverage(self.load(key), key.start_ms, key.end_ms)
