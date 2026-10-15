import pytest
from datetime import datetime,timezone
from decimal import Decimal as D
from meta_analyse.core import Level
from meta_analyse.level_quality import LevelReport
from meta_analyse.level_sync import LevelSync, PREFIX, signature

T=datetime(2026,1,1,tzinfo=timezone.utc)
L=Level(D("100"),"high",T,"H1")

class Terminal:
    def __init__(self):
        self.rows=[{"id":1,"note":"manual","price":"100"},
                   {"id":2,"note":PREFIX+"obsolete","price":"90"}]
        self.deleted=[]
    async def levels(self,conn,symbol):return list(self.rows)
    async def remove_level(self,conn,ident):
        self.deleted.append(ident)
        self.rows=[r for r in self.rows if r["id"]!=ident]
    async def add_level(self,conn,symbol,price,rule,note):
        self.rows.append({"id":3,"note":note,"price":price})

@pytest.mark.asyncio
async def test_replace_preserves_manual_and_removes_stale():
    t=Terminal()
    sync=LevelSync(t)
    report=LevelReport((L,),True,0,"ok")
    await sync.replace(1,"BTCUSDT",report,connection_verified=True,instrument_verified=True)
    assert t.deleted==[2]
    assert any(r["note"]=="manual" for r in t.rows)
    assert any(r["note"]==PREFIX+signature("BTCUSDT",L) for r in t.rows)

@pytest.mark.asyncio
async def test_crossing_deletes_only_owned():
    t=Terminal()
    sync=LevelSync(t)
    assert await sync.crossed(1,"BTCUSDT",D("80"),D("110"))==1
    assert t.deleted==[2]
    assert any(r["note"]=="manual" for r in t.rows)

@pytest.mark.asyncio
async def test_unverified_report_never_deletes():
    t=Terminal()
    with pytest.raises(ValueError):
        await LevelSync(t).replace(1,"BTCUSDT",LevelReport((),False,1,"missing"),
                                   connection_verified=True,instrument_verified=True)
    assert t.deleted==[]
