import pytest
from meta_analyse.flow_bridge import FlowBridge
from meta_analyse.trader_theme import TRADER_QSS

@pytest.mark.asyncio
async def test_bridge_snapshots_are_immutable_and_fail_closed():
    bridge=FlowBridge()
    await bridge.update("BTCUSDT",{"poc":"100","delta":"5","trusted":True},None)
    first=bridge.snapshot()
    assert first[0].quality=="UNVERIFIED"
    bridge.invalidate(["BTCUSDT"])
    assert first[0].symbol=="BTCUSDT"
    assert bridge.snapshot()[0].quality=="UNVERIFIED"

def test_theme_has_readable_table_and_selection_rules():
    assert "QTableWidget" in TRADER_QSS
    assert "selection-background-color" in TRADER_QSS
    assert "QTabBar::tab:selected" in TRADER_QSS
