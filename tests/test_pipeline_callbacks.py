import pytest
from decimal import Decimal as D
from meta_analyse.pipeline import RawPipeline
from meta_analyse.raw_trades import RawExecution

class DB:
    def __init__(self):self.saved=[]
    def save(self,event):
        self.saved.append(event)
        return True
    def gap(self,symbols,reason):pass

@pytest.mark.asyncio
async def test_pipeline_emits_execution_and_gap_callbacks():
    events=[]
    gaps=[]
    async def on_execution(event,*,contiguous):
        events.append((event.symbol,contiguous))
    async def on_gap(symbols,reason):
        gaps.append((symbols,reason))
    pipeline=RawPipeline(None,{"BTCUSDT":D("0.1")},on_execution=on_execution,on_gap=on_gap)
    pipeline.db=DB()
    await pipeline.execution(RawExecution("BTCUSDT","1",60000,D("100"),D("1"),"Buy"))
    await pipeline.gap(["BTCUSDT"],"disconnect")
    assert events and events[0][0]=="BTCUSDT"
    assert gaps==[(["BTCUSDT"],"disconnect")]
    assert not pipeline.aggregators["BTCUSDT"].quality["BTCUSDT"].contiguous
