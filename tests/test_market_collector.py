import pytest
from decimal import Decimal as D
from meta_analyse.orderbook import OrderBook
from meta_analyse.market_collector import MarketCollector

def msg(kind,u,seq,bids,asks):
    return {"type":kind,"data":{"s":"BTCUSDT","u":u,"seq":seq,"b":bids,"a":asks}}

def test_orderbook_crossed_snapshot_rejected():
    book=OrderBook("BTCUSDT")
    assert not book.apply(msg("snapshot",1,1,[["102","1"]],[["101","1"]]))
    assert not book.valid

def test_orderbook_delta_can_remove_wall_and_preserve_validity():
    book=OrderBook("BTCUSDT")
    assert book.apply(msg("snapshot",1,1,[["99","2000"],["98","1"]],[["101","1"]]))
    assert book.apply(msg("delta",2,2,[["99","0"]],[]))
    assert D("99") not in book.bids and book.valid

@pytest.mark.asyncio
async def test_market_collector_persists_before_callbacks():
    events=[]
    class DB:
        def book(self,*args):
            events.append("persist")
    collector=MarketCollector(None,None,on_book=lambda *args: record(*args))
    async def record(*args):
        events.append("callback")
    collector.db=DB()
    book=OrderBook("BTCUSDT")
    book.apply(msg("snapshot",1,1,[["99","1"]],[["101","1"]]))
    await collector._book("BTCUSDT",book,1000)
    assert events==["persist","callback"]
