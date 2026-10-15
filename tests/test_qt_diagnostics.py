"""Qt diagnostics table transitions with immutable worker snapshots."""
import asyncio
from dataclasses import replace
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
