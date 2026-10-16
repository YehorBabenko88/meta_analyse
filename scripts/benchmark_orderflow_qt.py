"""Offline Qt table benchmark; run with QT_QPA_PLATFORM=offscreen."""
from __future__ import annotations

import argparse
import json
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget
from meta_analyse.desktop import FlowTableItem


def measure(rows: int) -> dict:
    app = QApplication.instance() or QApplication([])
    table = QTableWidget(0, 7)
    values = ("1000", "2", "1", "1", "1", "0.333", "UNVERIFIED")
    started = time.perf_counter()
    table.setUpdatesEnabled(False)
    table.setSortingEnabled(False)
    try:
        table.setRowCount(rows)
        for row in range(rows):
            for column, value in enumerate(values):
                table.setItem(row, column, FlowTableItem(value))
    finally:
        table.setUpdatesEnabled(True)
    elapsed = time.perf_counter() - started
    # Model the frequent snapshot path: unchanged immutable rows must
    # skip the expensive per-cell population entirely.
    snapshot = tuple(range(rows))
    previous = snapshot
    started_unchanged = time.perf_counter()
    unchanged = snapshot is not previous and snapshot != previous
    unchanged_seconds = time.perf_counter() - started_unchanged
    assert not unchanged
    assert table.rowCount() == rows
    assert table.item(rows - 1, 6).text() == "UNVERIFIED"
    table.close()
    app.processEvents()
    return {"rows": rows, "cells": rows * 7, "populate_seconds": round(elapsed, 4), "unchanged_snapshot_seconds": round(unchanged_seconds, 8)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, nargs="+", default=[1000, 10000])
    args = parser.parse_args()
    if any(count <= 0 for count in args.rows):
        parser.error("row counts must be positive")
    print(json.dumps([measure(count) for count in args.rows], indent=2))


if __name__ == "__main__":
    main()
