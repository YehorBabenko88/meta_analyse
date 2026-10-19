from decimal import Decimal as D
import pytest
from meta_analyse.health import HealthTracker
from meta_analyse.raw_trades import RawExecution
from meta_analyse.pipeline import RawPipeline

def event():
    return RawExecution("BTCUSDT","id",60000,D("100"),D("1"),"Buy")

def test_health_does_not_claim_verified_profile():
    h=HealthTracker()
    h.record(event())
    h.gap("BTCUSDT")
    s=h.snapshot("BTCUSDT")
    assert s.received==1
    assert s.gap_count==1
    assert not s.profile_trusted

@pytest.mark.asyncio
async def test_pipeline_health_records_only_inserted_executions():
    class DB:
        def __init__(self):self.calls=0
        def save(self,e):
            self.calls+=1
            return self.calls==1
        def gap(self,s,r):pass
    p=RawPipeline(None,{"BTCUSDT":D("0.1")})
    p.db=DB()
    await p.execution(event())
    await p.execution(event())
    assert p.health.snapshot("BTCUSDT").received==1
