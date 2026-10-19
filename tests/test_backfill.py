import pytest
from datetime import datetime, timezone
from decimal import Decimal as D
from meta_analyse.backfill import BackfillCoordinator
from meta_analyse.instruments import Instrument
from meta_analyse.core import Candle

@pytest.mark.asyncio
async def test_backfill_uses_listing_time_not_arbitrary_window():
    class Exchange:
        async def candles(self,symbol,tf,start,end):
            assert start==1234567890000
            assert end==1234567899000
            yield [Candle(datetime(2009,2,13,tzinfo=timezone.utc),D("2"),D("1"),D("1"),D("2"))]
    class Store:
        def __init__(self):self.count=0
        def candle_batch(self,symbol,tf,page):self.count+=len(page)
    store=Store()
    c=BackfillCoordinator(Exchange(),store)
    report=await c.instrument(Instrument("ABCUSDT",D("0.01"),1234567890000,"Trading"),
                              1234567899000,("D1",))
    assert store.count==1
    assert report["D1"]["verified_complete"] is False
