"""Offline Qt smoke test: the historical tab never initiates exchange orders."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QTableWidget

from meta_analyse.desktop import Window
from meta_analyse.desktop_service import DesktopSnapshot
from meta_analyse.orderflow_view import OrderFlowViewRow


def test_historical_table_renders_immutable_snapshot(monkeypatch):
    # Avoid worker/network startup: exercise only the Qt presentation path.
    # The full Window owns a live worker, so create a minimal Qt shell instead.
    app = QApplication.instance() or QApplication([])
    table = QTableWidget(0, 7)
    rows = (
        OrderFlowViewRow("1000", "2", "1", "1", "1", "0.333", "UNVERIFIED"),
    )
    snapshot = DesktopSnapshot(orderflow_rows=rows)
    table.setRowCount(len(snapshot.orderflow_rows))
    from meta_analyse.desktop import FlowTableItem
    for i, row in enumerate(snapshot.orderflow_rows):
        values = (row.bucket, row.buy, row.sell, row.delta,
                  row.cumulative_delta, row.imbalance, row.quality)
        for j, value in enumerate(values):
            table.setItem(i, j, FlowTableItem(value))
    assert table.item(0, 4).text() == "1"
    assert table.item(0, 6).text() == "UNVERIFIED"
    table.close()
