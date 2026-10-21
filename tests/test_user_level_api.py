import pytest
from meta_analyse.ports import MetaScalp

@pytest.mark.asyncio
async def test_plain_levels_use_user_levels_api_only():
    api=MetaScalp()
    calls=[]
    async def request(method,path,**kwargs):
        calls.append((method,path,kwargs))
        return []
    api.request=request
    await api.levels(1,"BTCUSDT")
    await api.add_level(1,"BTCUSDT","100","GreaterThanEqual","meta_analyse:test")
    await api.remove_level(1,42)
    await api.close()
    assert all("/user-levels" in path for _,path,_ in calls)
    assert all("/signal-levels" not in path for _,path,_ in calls)
    assert calls[1][2]["json"]["note"]=="meta_analyse:test"
    assert "triggerRule" not in calls[1][2]["json"]
