import pytest
from datetime import datetime,timezone
from decimal import Decimal as D
from meta_analyse.core import Level
from meta_analyse.level_quality import LevelReport
from meta_analyse.durable_sync import DurableLevelSync

class Journal:
    def __init__(self):self.events=[]
    def mark(self,*args):self.events.append(args)

class Terminal:
    def __init__(self,fail=False):
        self.rows=[]
        self.fail=fail
    async def levels(self,c,s):return self.rows
    async def add_level(self,c,s,p,r,n):
        if self.fail:raise ConnectionError("disconnected")
        self.rows.append({"id":1,"note":n,"price":p})
    async def remove_level(self,c,i):self.rows=[]

@pytest.mark.asyncio
async def test_journal_verified_only_after_terminal_readback():
    t=Terminal()
    j=Journal()
    report=LevelReport((Level(D("100"),"high",datetime(2026,1,1,tzinfo=timezone.utc),"H1"),),True,0,"ok")
    await DurableLevelSync(t,j).replace(1,"BTCUSDT",report,
                                      connection_verified=True,instrument_verified=True)
    assert [x[3] for x in j.events]==["pending","verified"]

@pytest.mark.asyncio
async def test_network_failure_records_failed_not_verified():
    t=Terminal(fail=True)
    j=Journal()
    report=LevelReport((Level(D("100"),"high",datetime(2026,1,1,tzinfo=timezone.utc),"H1"),),True,0,"ok")
    with pytest.raises(ConnectionError):
        await DurableLevelSync(t,j).replace(1,"BTCUSDT",report,
                                          connection_verified=True,instrument_verified=True)
    assert [x[3] for x in j.events]==["pending","failed"]
