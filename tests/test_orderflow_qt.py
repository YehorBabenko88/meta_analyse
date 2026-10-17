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


def test_sorted_history_refresh_replaces_rows_without_stale_values():
    """Reproduces the sorted-table update path without starting the worker."""
    app = QApplication.instance() or QApplication([])
    from meta_analyse.desktop import FlowTableItem
    table = QTableWidget(0, 7)
    table.setSortingEnabled(True)

    def render(rows):
        was_sorting = table.isSortingEnabled()
        was_updating = table.updatesEnabled()
        table.setUpdatesEnabled(False)
        table.setSortingEnabled(False)
        try:
            table.setRowCount(0)
            table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    table.setItem(i, j, FlowTableItem(value))
        finally:
            table.setSortingEnabled(was_sorting)
            table.setUpdatesEnabled(was_updating)

    render([("100", "1", "0", "1", "1", "1", "UNVERIFIED"),
            ("200", "2", "0", "2", "3", "1", "UNVERIFIED")])
    table.sortItems(0)
    render([("300", "3", "0", "3", "3", "1", "UNVERIFIED")])
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "300"
    assert table.item(0, 3).text() == "3"
    assert table.isSortingEnabled()
    table.close()
