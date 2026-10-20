import asyncio,json
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from meta_analyse import orderbook_stream as module
async def main():
    stop=asyncio.Event();seen=[];gaps=[];connections=[]
    def frame(kind,u,size='1'):
        return dict(topic='orderbook.50.BTCUSDT',type=kind,ts=1,data=dict(s='BTCUSDT',u=u,seq=u,b=[['100',size]],a=[['102','1']]))
    frames=iter([frame('snapshot',10),frame('delta',11,'NaN'),frame('delta',12)])
    class Socket:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):return False
        async def send(self,text):pass
        async def recv(self):return json.dumps(next(frames))
    def connect(*args,**kwargs):connections.append(1);return Socket()
    async def book(symbol,state,ts):seen.append(state.update_id)
    async def gap(symbols,reason):
        gaps.append(reason)
        if len(gaps)==3:stop.set()
    stream=module.OrderBookStream(book,gap)
    with patch.object(module.websockets,'connect',connect):await asyncio.wait_for(stream.run(['BTCUSDT'],stop),2)
    assert seen==[10] and len(connections)==1 and not stream.books['BTCUSDT'].valid
    result={'candidate_sha':'13901274dac527f0aacfaf48481414b0971d6012','invalid_delta_fail_closed':True,'automatic_resubscription':False,'recovery_without_snapshot':'NOT_RECOVERED','connections':len(connections),'published_updates':seen,'verdict':'NO-GO for autonomous recovery requirement; no false-valid state observed'}
    Path('../commission-evidence/orderbook-liveness.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
asyncio.run(main())
