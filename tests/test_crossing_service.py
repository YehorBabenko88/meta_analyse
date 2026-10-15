import pytest
from decimal import Decimal as D
from meta_analyse.crossing_service import CrossingService
from meta_analyse.raw_trades import RawExecution

class Sync:
    def __init__(self):self.calls=[]
    async def crossed(self,c,s,p,n):
        self.calls.append((c,s,p,n))
        return 1

def trade(i,p):
    return RawExecution("BTCUSDT",str(i),i,D(p),D("1"),"Buy")

@pytest.mark.asyncio
async def test_contiguous_execution_calls_terminal_crossing():
    sync=Sync()
    service=CrossingService(sync,lambda s:7)
    assert await service.execution(trade(1,"90"),contiguous=True)==0
    assert await service.execution(trade(2,"110"),contiguous=True)==1
    assert sync.calls==[(7,"BTCUSDT",D("90"),D("110"))]

@pytest.mark.asyncio
async def test_gap_prevents_bridging_prices():
    sync=Sync()
    service=CrossingService(sync,lambda s:7)
    await service.execution(trade(1,"90"),contiguous=True)
    service.gap("BTCUSDT")
    await service.execution(trade(2,"110"),contiguous=True)
    assert sync.calls==[]

@pytest.mark.asyncio
async def test_unverified_execution_clears_anchor():
    sync=Sync()
    service=CrossingService(sync,lambda s:7)
    await service.execution(trade(1,"90"),contiguous=True)
    await service.execution(trade(2,"110"),contiguous=False)
    await service.execution(trade(3,"120"),contiguous=True)
    assert sync.calls==[]
