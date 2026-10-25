import asyncio
from decimal import Decimal as D
import pytest
from meta_analyse.pipeline import RawPipeline
from meta_analyse.raw_trades import RawExecution
from meta_analyse.instruments import instruments

class DB:
    def __init__(self): self.ids=set()
    def initialize(self): pass
    def save(self,e):
        key=(e.symbol,e.execution_id)
        if key in self.ids: return False
        self.ids.add(key)
        return True
    def gap(self,symbols,reason): pass

@pytest.mark.asyncio
async def test_pipeline_durable_before_aggregation():
    p=RawPipeline(object(),{"BTCUSDT":D("0.1")})
    db=DB()
    p.db=db
    event=RawExecution("BTCUSDT","id-1",60000,D("100"),D("2"),"Buy")
    await p.execution(event)
    await p.execution(event)
    assert len(db.ids)==1
    assert p.aggregators["BTCUSDT"].minutes["BTCUSDT"].volume==D("2")

@pytest.mark.asyncio
async def test_pipeline_gap_invalidates_minute():
    p=RawPipeline(object(),{"BTCUSDT":D("0.1")})
    p.db=DB()
    await p.execution(RawExecution("BTCUSDT","id-1",60000,D("100"),D("2"),"Buy"))
    await p.gap(["BTCUSDT"],"connection reset")
    assert not p.aggregators["BTCUSDT"].quality["BTCUSDT"].contiguous
    assert "BTCUSDT" not in p.aggregators["BTCUSDT"].minutes


@pytest.mark.asyncio
async def test_pipeline_rejects_duplicate_start_without_spawning_extra_stream(monkeypatch):
    class Stream:
        def __init__(self, *_):
            pass
        async def run(self, symbols, stop):
            await stop.wait()
    monkeypatch.setattr("meta_analyse.pipeline.RawTradeStream", Stream)
    pipeline = RawPipeline(None, {"BTCUSDT": D("0.1")})
    pipeline.db = DB()
    await pipeline.start()
    try:
        with pytest.raises(RuntimeError, match="already started"):
            await pipeline.start()
        assert len(pipeline.tasks) == 1
    finally:
        await pipeline.stop()


@pytest.mark.asyncio
async def test_pipeline_database_failure_records_health_gap_before_propagating():
    class FailingDB(DB):
        def save(self, event):
            raise OSError("synthetic rollback")
    pipeline = RawPipeline(None, {"BTCUSDT": D("0.1")})
    pipeline.db = FailingDB()
    with pytest.raises(OSError, match="synthetic rollback"):
        await pipeline.execution(RawExecution("BTCUSDT", "1", 60000, D("100"), D("1"), "Buy"))
    health = pipeline.health.snapshot("BTCUSDT")
    assert health.gap_count == 1
    assert health.received == 0

@pytest.mark.asyncio
async def test_instrument_cursor_and_tick_size():
    class API:
        async def get(self,path,params):
            if "cursor" not in params:
                return {"list":[{"symbol":"AAAUSDT","status":"Trading","launchTime":"1234567890",
                  "priceFilter":{"tickSize":"0.001"}}],"nextPageCursor":"next"}
            return {"list":[],"nextPageCursor":""}
    result=await instruments(API())
    assert result["AAAUSDT"].tick_size==D("0.001")
    assert result["AAAUSDT"].launch_ms==1234567890
