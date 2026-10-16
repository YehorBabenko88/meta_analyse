"""Stream-validation of downloaded Bybit public trade archives.

A valid gzip/CSV is not proof of complete market history; coverage remains
unverified until an independent completeness source is available.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import csv
import gzip
from pathlib import Path


@dataclass(frozen=True)
class ArchiveAudit:
    rows: int
    first_ms: int | None
    last_ms: int | None
    valid: bool
    complete: bool
    reason: str


def audit_trade_gzip(path: str | Path, *, max_rows: int = 50_000_000) -> ArchiveAudit:
    if max_rows < 1:
        raise ValueError("max_rows must be positive")
    rows = 0
    first = last = None
    try:
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = set(reader.fieldnames or ())
            if not {"timestamp", "price", "size"}.issubset(fields):
                return ArchiveAudit(0, None, None, False, False, "required columns missing")
            for record in reader:
                rows += 1
                if rows > max_rows:
                    return ArchiveAudit(rows, first, last, False, False, "row budget exceeded")
                try:
                    raw_ts = Decimal(record["timestamp"])
                    price = Decimal(record["price"])
                    size = Decimal(record["size"])
                    if not raw_ts.is_finite() or not price.is_finite() or not size.is_finite():
                        raise ValueError("nonfinite numeric value")
                    if raw_ts < 0 or price <= 0 or size <= 0:
                        raise ValueError("invalid trade values")
                    # Bybit archive timestamps are in seconds, often fractional.
                    timestamp_ms = int(raw_ts * 1000)
                    if last is not None and timestamp_ms < last:
                        raise ValueError("out-of-order trades")
                except (ValueError, TypeError, InvalidOperation, KeyError) as exc:
                    return ArchiveAudit(rows, first, last, False, False, f"invalid row: {exc}")
                if first is None:
                    first = timestamp_ms
                last = timestamp_ms
    except (OSError, EOFError, UnicodeError, csv.Error) as exc:
        return ArchiveAudit(rows, first, last, False, False, f"corrupt archive: {exc}")
    if not rows:
        return ArchiveAudit(0, None, None, False, False, "empty archive")
    return ArchiveAudit(rows, first, last, True, False,
                        "parsed successfully; completeness not independently verified")
