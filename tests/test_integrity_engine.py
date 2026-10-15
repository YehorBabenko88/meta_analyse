from decimal import Decimal as D
from meta_analyse.integrity import ExecutionAggregator
from meta_analyse.raw_trades import RawExecution

def execution(id, timestamp, price="100"):
    return RawExecution("BTCUSDT",id,timestamp,D(price),D("1"),"Buy")

def test_deduplicated_and_actual_poc():
    a=ExecutionAggregator(D("0.01"))
    a.accept(execution("a",60000,"100"))
    a.accept(execution("a",60000,"100"))
    a.accept(execution("b",60001,"101"))
    a.accept(execution("c",60002,"101"))
    assert a.minutes["BTCUSDT"].poc == D("101")
    assert a.quality["BTCUSDT"].duplicates == 1

def test_gap_discards_partial_candle():
    a=ExecutionAggregator(D("0.01"))
    a.accept(execution("a",60000))
    a.gap(["BTCUSDT"],"reconnect")
    assert "BTCUSDT" not in a.minutes
    assert not a.quality["BTCUSDT"].contiguous

def test_out_of_order_is_not_invented():
    a=ExecutionAggregator(D("0.01"))
    a.accept(execution("a",60002))
    assert a.accept(execution("b",60001)) is None
    assert a.quality["BTCUSDT"].out_of_order == 1
