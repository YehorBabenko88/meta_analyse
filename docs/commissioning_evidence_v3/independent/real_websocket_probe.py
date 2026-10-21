import asyncio,json,subprocess
from pathlib import Path
import websockets
from meta_analyse.orderbook_stream import OrderBookStream
SHA='446c72bd97cacc31f9937c9ab941d11539733be4'
def packet(kind,u,seq,size='1'):
 return json.dumps(dict(topic='orderbook.50.BTCUSDT',type=kind,ts=1,data=dict(s='BTCUSDT',u=u,seq=seq,b=[['100',size]],a=[['101','1']])))
async def case(mode):
 stop=asyncio.Event();first_seen=asyncio.Event();published=[];gaps=[];opened=[];closed=[]
 async def handler(ws):
  index=len(opened)+1;opened.append(index)
  try:
   request=json.loads(await ws.recv());assert request['op']=='subscribe'
   if index==1:
    await ws.send(packet('snapshot',1,1));await first_seen.wait()
    if mode=='invalid':await ws.send(packet('delta',2,2,'NaN'));await ws.send(packet('delta',3,3))
    elif mode=='sequence':await ws.send(packet('delta',2,1));await ws.send(packet('delta',3,3))
    elif mode=='busy':
     while not ws.state.name=='CLOSED':
      await ws.send(json.dumps({'topic':'publicTrade.OTHER','data':[]}));await asyncio.sleep(.001)
   else:await ws.send(packet('snapshot',10,10))
   await ws.wait_closed()
  except websockets.ConnectionClosed:pass
  finally:closed.append(index)
 async def book(symbol,b,ts):
  published.append(b.update_id)
  if b.update_id==1:first_seen.set()
  if b.update_id==10:stop.set()
 async def gap(symbols,reason):gaps.append(reason)
 async with websockets.serve(handler,'127.0.0.1',0) as server:
  port=server.sockets[0].getsockname()[1]
  stream=OrderBookStream(book,gap,url=f'ws://127.0.0.1:{port}',silence_timeout=.05,backoff_base=.005,backoff_max=.01)
  await asyncio.wait_for(stream.run(['BTCUSDT'],stop),3)
 assert published==[1,10] and opened==[1,2] and sorted(closed)==[1,2],(mode,published,opened,closed)
 return dict(mode=mode,published=published,opened=opened,closed=closed,epochs=stream.connection_epoch,unverified_gap=any('UNVERIFIED' in x for x in gaps))
async def main():
 result={'sha':SHA,'actual_source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'transport':'real loopback WebSocket server, no public market/network/DB','cases':[]}
 assert result['actual_source_sha']==SHA
 for mode in ['invalid','sequence','silent','busy']:result['cases'].append(await case(mode))
 Path('../reaudit-evidence/real-websocket-results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
asyncio.run(main())
