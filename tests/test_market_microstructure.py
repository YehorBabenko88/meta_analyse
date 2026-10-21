import pytest
from decimal import Decimal as D
from meta_analyse.orderbook import OrderBook
from meta_analyse.wall_tracker import WallTracker
from meta_analyse.tape_velocity import TapeVelocity
from meta_analyse.raw_trades import RawExecution
from meta_analyse.open_interest import parse_oi

def bookmsg(kind,u,seq,bids,asks):
    return {"type":kind,"data":{"s":"BTCUSDT","u":u,"seq":seq,"b":bids,"a":asks}}

def test_book_requires_snapshot_and_resets_on_replay():
    b=OrderBook("BTCUSDT")
    assert not b.apply(bookmsg("delta",2,2,[["99","1"]],[["101","1"]]))
    assert b.apply(bookmsg("snapshot",1,1,[["99","1"]],[["101","1"]]))
    assert b.apply(bookmsg("delta",3,3,[["99","2"]],[]))
    assert not b.apply(bookmsg("delta",3,3,[],[]))
    assert not b.valid

def test_ephemeral_wall_warning_is_not_spoofing_verdict():
    b=OrderBook("BTCUSDT")
    b.apply(bookmsg("snapshot",1,1,[["99","2000"],["98","1"]],[["101","1"]]))
    w=WallTracker(min_notional=D("100000"))
    assert not w.observe(b,1000)
    b.apply(bookmsg("delta",2,2,[["99","0"]],[]))
    alerts=w.observe(b,1100)
    assert len(alerts)==1
    assert alerts[0].confidence=="unverified_cancellation_or_execution"

def test_tape_velocity_fail_closed_after_gap():
    t=TapeVelocity(D("0.1"))
    e=RawExecution("BTCUSDT","1",1000,D("100"),D("2"),"Buy")
    assert t.add(e,D("100"),contiguous=True).trusted
    assert not t.add(e,D("100"),contiguous=False).trusted

def test_open_interest_parsing():
    assert parse_oi("BTCUSDT",[{"timestamp":"1000","openInterest":"12.5"}])[0].open_interest==D("12.5")
