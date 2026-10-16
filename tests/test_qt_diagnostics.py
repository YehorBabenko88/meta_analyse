"""Qt diagnostics table transitions with immutable worker snapshots."""
import asyncio
from dataclasses import replace
from PySide6.QtCore import Qt
import pytest
from meta_analyse.desktop import Window
from meta_analyse.desktop_service import DesktopSnapshot
from meta_analyse.freshness_style import freshness_colors
from test_windows_smoke import until

@pytest.mark.asyncio
async def test_diagnostics_color_transitions_and_disconnect(monkeypatch, app):
    monkeypatch.delenv("META_ANALYSE_DSN", raising=False)
    window = Window()
    window.show()
    try:
        await until(app, lambda: window.worker.is_alive())
        def publish(age):
            window._snapshot = DesktopSnapshot(
                flow_state="connected",
                market_events=(("orderbook:BTCUSDT", 3),),
                market_gaps=(("orderbook:BTCUSDT", 1),),
                market_ages=(("orderbook:BTCUSDT", age),),
            )
            window.repaint_state()
            item = window.diagnostics_table.item(0, 4)
            assert item is not None
            assert item.foreground().color().name() == freshness_colors(age)[0].lower()
            assert item.background().color().name() == freshness_colors(age)[1].lower()
            return item
        assert publish(0.0).text() == "FRESH"
        assert publish(2.0).text() == "DELAYED"
        assert publish(10.0).text() == "STALE"
        assert window.diagnostics_table.item(0, 1).text() == "3"
        assert window.diagnostics_table.item(0, 2).text() == "1"
        window._snapshot = replace(window._snapshot, flow_state="disconnected",
                                   market_events=(), market_gaps=(), market_ages=())
        window.repaint_state()
        assert window.diagnostics_table.rowCount() == 0
        assert "counters hidden" in window.diagnostics_state.text()
    finally:
        window.close()
        await until(app, lambda: not window.worker.is_alive() and not window.isVisible())

@pytest.mark.asyncio
async def test_diagnostics_sorting_preserves_feed_identity(monkeypatch, app):
    monkeypatch.delenv("META_ANALYSE_DSN", raising=False)
    window = Window()
    window.show()
    try:
        await until(app, lambda: window.worker.is_alive())
        window._snapshot = DesktopSnapshot(
            flow_state="connected",
            market_events=(("orderbook:BTCUSDT", 5), ("orderbook:ETHUSDT", 9)),
            market_ages=(("orderbook:BTCUSDT", 0.5), ("orderbook:ETHUSDT", 12.0)),
        )
        window.repaint_state()
        table = window.diagnostics_table
        table.sortItems(0, Qt.SortOrder.DescendingOrder)  # Reverse symbol order.
        window._snapshot = replace(window._snapshot,
            market_events=(("orderbook:BTCUSDT", 7), ("orderbook:ETHUSDT", 10)),
            market_ages=(("orderbook:BTCUSDT", 11.0), ("orderbook:ETHUSDT", 1.0)))
        window.repaint_state()
        rows = {table.item(i, 0).text(): i for i in range(table.rowCount())}
        assert table.item(rows["orderbook:BTCUSDT"], 1).text() == "7"
        assert table.item(rows["orderbook:BTCUSDT"], 4).text() == "STALE"
        assert table.item(rows["orderbook:ETHUSDT"], 1).text() == "10"
        assert table.item(rows["orderbook:ETHUSDT"], 4).text() == "FRESH"
        assert table.item(rows["orderbook:BTCUSDT"], 4).foreground().color().name() == freshness_colors(11.0)[0].lower()
    finally:
        window.close()
        await until(app, lambda: not window.worker.is_alive() and not window.isVisible())

@pytest.mark.asyncio
async def test_diagnostics_feed_add_remove_and_new_session(monkeypatch, app):
    monkeypatch.delenv("META_ANALYSE_DSN", raising=False)
    window = Window()
    window.show()
    try:
        await until(app, lambda: window.worker.is_alive())
        def update(events, ages, state="connected"):
            window._snapshot = DesktopSnapshot(
                flow_state=state, market_events=events, market_ages=ages)
            window.repaint_state()
            table = window.diagnostics_table
            return {table.item(i, 0).text(): (
                table.item(i, 1).text(), table.item(i, 4).text())
                for i in range(table.rowCount())}
        first = update((("orderbook:BTCUSDT", 50),),
                       (("orderbook:BTCUSDT", 0.1),))
        assert first == {"orderbook:BTCUSDT": ("50", "FRESH")}
        second = update((("orderbook:BTCUSDT", 51), ("orderbook:ETHUSDT", 1)),
                        (("orderbook:BTCUSDT", 3.0), ("orderbook:ETHUSDT", 0.0)))
        assert second == {"orderbook:BTCUSDT": ("51", "DELAYED"),
                          "orderbook:ETHUSDT": ("1", "FRESH")}
        assert update((), (), state="disconnected") == {}
        # A fresh connection must not retain counters or colors from old session.
        assert update((("orderbook:ETHUSDT", 1),),
                      (("orderbook:ETHUSDT", 11.0),)) == {
                          "orderbook:ETHUSDT": ("1", "STALE")}
        assert update((("orderbook:ETHUSDT", 2),),
                      (("orderbook:ETHUSDT", 0.0),)) == {
                          "orderbook:ETHUSDT": ("2", "FRESH")}
    finally:
        window.close()
        await until(app, lambda: not window.worker.is_alive() and not window.isVisible())

@pytest.mark.asyncio
async def test_diagnostics_mixed_feed_cadences_and_sort(monkeypatch, app):
    """Qt must classify identical ages differently for stream and polled feeds."""
    monkeypatch.delenv("META_ANALYSE_DSN", raising=False)
    window = Window()
    window.show()
    try:
        await until(app, lambda: window.worker.is_alive())
        table = window.diagnostics_table
        window._snapshot = DesktopSnapshot(
            flow_state="connected",
            market_events=(("orderbook:BTCUSDT", 100), ("open_interest:BTCUSDT", 2)),
            market_ages=(("orderbook:BTCUSDT", 300.0),
                         ("open_interest:BTCUSDT", 300.0)),
        )
        window.repaint_state()
        table.sortItems(0, Qt.SortOrder.DescendingOrder)
        rows = {table.item(i, 0).text(): i for i in range(table.rowCount())}
        assert table.item(rows["orderbook:BTCUSDT"], 4).text() == "STALE"
        assert table.item(rows["open_interest:BTCUSDT"], 4).text() == "FRESH"
        window._snapshot = replace(
            window._snapshot,
            market_ages=(("orderbook:BTCUSDT", 0.0),
                         ("open_interest:BTCUSDT", 400.0)),
        )
        window.repaint_state()
        rows = {table.item(i, 0).text(): i for i in range(table.rowCount())}
        assert table.item(rows["orderbook:BTCUSDT"], 4).text() == "FRESH"
        assert table.item(rows["open_interest:BTCUSDT"], 4).text() == "DELAYED"
        from meta_analyse.freshness_style import freshness_colors_for_feed
        for key, age in (("orderbook:BTCUSDT", 0.0),
                         ("open_interest:BTCUSDT", 400.0)):
            item = table.item(rows[key], 4)
            fg, bg = freshness_colors_for_feed(key, age)
            assert item.foreground().color().name() == fg.lower()
            assert item.background().color().name() == bg.lower()
    finally:
        window.close()
        await until(app, lambda: not window.worker.is_alive() and not window.isVisible())

@pytest.mark.asyncio
async def test_diagnostics_numeric_sort_and_read_only_tables(monkeypatch, app):
    from PySide6.QtWidgets import QAbstractItemView
    monkeypatch.delenv("META_ANALYSE_DSN", raising=False)
    window = Window()
    try:
        assert window.flow_table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
        assert window.diagnostics_table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
        window._snapshot = DesktopSnapshot(flow_state="connected",
            market_events=(("orderbook:A", 2), ("orderbook:B", 100), ("orderbook:C", 10)),
            market_ages=(("orderbook:A", 100.), ("orderbook:B", 10.), ("orderbook:C", 2.)))
        window.repaint_state()
        table = window.diagnostics_table
        for column, expected in ((1, ["2", "10", "100"]), (3, ["2.0", "10.0", "100.0"])):
            table.sortItems(column, Qt.SortOrder.AscendingOrder)
            assert [table.item(i, column).text() for i in range(3)] == expected
    finally:
        window.close()
        await until(app, lambda: not window.worker.is_alive() and not window.isVisible())
