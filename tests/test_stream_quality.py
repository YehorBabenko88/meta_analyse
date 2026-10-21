from decimal import Decimal as D
from meta_analyse.integrity import ExecutionAggregator
from meta_analyse.raw_trades import RawExecution

def e(id,ms):
    return RawExecution("BTCUSDT",id,ms,D("100"),D("1"),"Buy")

def test_live_stream_never_certifies_full_minute_without_proof():
    a=ExecutionAggregator(D("0.01"))
    a.accept(e("one",60000))
    a.accept(e("two",120000))
    assert not a.minutes["BTCUSDT"].complete
    assert not a.closed

def test_out_of_order_invalidates_partial_minute():
    a=ExecutionAggregator(D("0.01"))
    a.accept(e("one",60002))
    a.accept(e("two",60001))
    assert a.quality["BTCUSDT"].out_of_order==1
    assert "BTCUSDT" not in a.minutes
