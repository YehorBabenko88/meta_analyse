import pytest
from decimal import Decimal as D
from meta_analyse.analysis_session import AnalysisSession
from meta_analyse.orderbook import OrderBook
from meta_analyse.liquidity import large_levels
from meta_analyse.raw_trades import RawExecution

def trade():
    return RawExecution("BTCUSDT","1",1000,D("100"),D("2"),"Buy")

@pytest.mark.asyncio
async def test_session_routes_trade_into_footprint_and_tape():
    seen=[]
    async def on_update(symbol,footprint,tape):
        seen.append((symbol,footprint,tape))
    session=AnalysisSession(None,None,{"BTCUSDT":D("0.5")},on_update=on_update)
    session.select_level("BTCUSDT",D("100"))
    await session._execution(trade(),contiguous=True)
    assert seen[0][1]["prices"]["100.0"]["buy"]=="2"
    assert seen[0][2].trusted
    await session._trade_gap(["BTCUSDT"],"disconnect")
    assert not session.analysis.clock.align("BTCUSDT",1000).valid

def test_liquidity_near_level_uses_relative_baseline():
    book=OrderBook("BTCUSDT")
    assert book.apply({"type":"snapshot","data":{"s":"BTCUSDT","u":1,"seq":1,
        "b":[["99","2000"],["98","1"]],"a":[["101","1"],["102","1"]]}})
    signals=large_levels(book,D("100"),D("1"))
    assert len(signals)==1
    assert signals[0].price==D("99")
