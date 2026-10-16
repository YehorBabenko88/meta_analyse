"""Validate chronological trade archives before granting coverage credit.

Checks are deliberately conservative: timestamp monotonicity and row schema
are necessary, but never sufficient to prove that *all* exchange trades exist.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class TradeAudit:
    rows: int
    first_ms: int | None
    last_ms: int | None
    chronology_ok: bool
    complete: bool
    reason: str


def audit_trade_csv(path: str | Path, start_ms: int, end_ms: int,
                    *, timestamp_column: str = "timestamp",
                    price_column: str = "price",
                    quantity_column: str = "size") -> TradeAudit:
    if start_ms >= end_ms:
        raise ValueError("invalid audit interval")
    first = last = None
    rows = 0
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {timestamp_column, price_column, quantity_column}.issubset(reader.fieldnames):
            raise ValueError("missing trade columns")
        for row in reader:
            try:
                timestamp = int(row[timestamp_column])
                price = Decimal(row[price_column])
                quantity = Decimal(row[quantity_column])
            except (ValueError, TypeError, InvalidOperation, KeyError) as exc:
                raise ValueError(f"invalid trade row {rows + 1}") from exc
            if not start_ms <= timestamp < end_ms:
                raise ValueError(f"trade timestamp outside requested interval at row {rows + 1}")
            if not price.is_finite() or not quantity.is_finite() or price <= 0 or quantity <= 0:
                raise ValueError(f"invalid trade price or size at row {rows + 1}")
            if last is not None and timestamp < last:
                raise ValueError(f"out-of-order trade timestamp at row {rows + 1}")
            if first is None:
                first = timestamp
            last = timestamp
            rows += 1
    return TradeAudit(rows, first, last, True, False,
                      "Row validity does not prove absence of missing trades; exchange sequence or trusted archive guarantees required")
