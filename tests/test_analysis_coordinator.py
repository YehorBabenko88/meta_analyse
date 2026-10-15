import pytest
from decimal import Decimal as D
from meta_analyse.market_clock import MarketClock
from meta_analyse.footprint_engine import FootprintEngine
from meta_analyse.analysis_coordinator import AnalysisCoordinator
from meta_analyse.raw_trades import RawExecution

def trade(i,t,p,side):
    return RawExecution("BTCUSDT",str(i),t,D(p),D("2"),side)

def test_clock_requires_fresh_aligned_verified_feeds():
    clock=MarketClock(max_skew_ms=500,max_age_ms=1000)
    clock.observe("trades","BTCUSDT",1000,trusted=True)
    clock.observe("orderbook","BTCUSDT",1200,trusted=True)
    assert clock.align("BTCUSDT",1300).valid
    assert not clock.align("BTCUSDT",3000).valid
    clock.gap("orderbook","BTCUSDT")
    assert not clock.align("BTCUSDT",1300).valid

def test_footprint_aggregates_taker_buy_sell_by_tick():
    engine=FootprintEngine({"BTCUSDT":D("0.5")})
    engine.execution(trade(1,1000,"100","Buy"),contiguous=True)
    result=engine.execution(trade(2,1100,"100","Sell"),contiguous=True)
    assert result.poc==D("100")
    assert result.delta==0
    assert result.cells[D("100")].count==2

def test_footprint_gap_invalidates_closed_bar():
    engine=FootprintEngine({"BTCUSDT":D("0.5")})
    engine.execution(trade(1,1000,"100","Buy"),contiguous=True)
    engine.gap("BTCUSDT")
    assert not engine.closed[-1].trusted

@pytest.mark.asyncio
async def test_coordinator_routes_tape_and_footprint():
    a=AnalysisCoordinator({"BTCUSDT":D("0.5")})
    a.set_level("BTCUSDT",D("100"))
    footprint,tape=await a.execution(trade(1,1000,"100","Buy"),contiguous=True)
    assert footprint.cells[D("100")].buy==2
    assert tape.trusted
    await a.gap(["BTCUSDT"],"disconnect")
    assert not a.clock.align("BTCUSDT",1000).valid
