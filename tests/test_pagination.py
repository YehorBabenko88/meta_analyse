from datetime import datetime,timezone
from decimal import Decimal as D
import pytest
from meta_analyse.exchange import BybitPublic

@pytest.mark.asyncio
async def test_short_kline_page_does_not_end_history():
    api=BybitPublic()
    calls=[]
    async def fake_get(path,params):
        calls.append(params["end"])
        if len(calls)==1:
            return {"list":[["3000","1","2","1","1","1"]]}
        if len(calls)==2:
            return {"list":[["2000","1","2","1","1","1"]]}
        return {"list":[]}
    api.get=fake_get
    batches=[]
    async for page in api.candles("BTCUSDT","M1",1000,4000):
        batches.extend(page)
    await api.close()
    assert len(calls)==3
    assert len(batches)==2
    assert batches[0].start < batches[1].start or len(batches)==2
