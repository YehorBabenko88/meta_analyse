"""Regression tests for orderbook-to-UI summaries without exchange connectivity."""
from decimal import Decimal as D
import pytest
from meta_analyse.orderbook import OrderBook
from meta_analyse.book_summary import summarize_book
from meta_analyse.flow_bridge import FlowBridge
from meta_analyse.tape_velocity import TapeSnapshot

def _book():
    book=OrderBook("BTCUSDT")
    assert book.apply({"type":"snapshot","data":{"s":"BTCUSDT","u":10,"seq":10,
        "b":[["99","2000"],["98","1"],["97","1"]],"a":[["101","1000"],["102","1"],["103","1"]]}})
    return book

def test_book_summary_spread_and_nearby_wall():
    book=_book()
    summary=summarize_book(book,D("1"),D("100"))
    assert summary.valid
    assert summary.spread_ticks==D("2")
    assert summary.bid_notional==D("198195")
    assert summary.ask_notional==D("101205")
    assert summary.largest_nearby
    assert summary.largest_nearby[0].side=="bid"

def test_book_summary_fails_closed_for_crossed_book():
    book=_book()
    book.asks[D("97")]=D("1")
    assert not summarize_book(book,D("1")).valid

def test_book_summary_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        summarize_book(_book(),D("0"))
    with pytest.raises(ValueError):
        summarize_book(_book(),D("1"),max_walls=-1)

@pytest.mark.asyncio
async def test_flow_hides_book_metrics_after_gap():
    bridge=FlowBridge()
    tape=TapeSnapshot(D("1"),D("10"),D("10"),D("0"),D("0"),True)
    await bridge.update("BTCUSDT",{"poc":"100","delta":"1","trusted":True},tape)
    bridge.trade_observed("BTCUSDT")
    bridge.book_observed("BTCUSDT",summarize_book(_book(),D("1"),D("100")))
    row=bridge.snapshot()[0]
    assert row.quality=="PROVISIONAL"
    assert row.spread=="2"
    assert row.imbalance!="—"
    bridge.source_gap("orderbook",["BTCUSDT"])
    row=bridge.snapshot()[0]
    assert row.quality=="UNVERIFIED"
    assert row.spread==row.imbalance==row.wall=="—"
