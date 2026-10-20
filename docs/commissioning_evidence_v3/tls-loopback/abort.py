import asyncio,sys,pathlib,json
root=pathlib.Path(r'C:/Users/LS-5/Documents/Codex/2026-10-15/github-https-github-com-yehorbabenko88-meta/work/windows-commissioning-audit');sys.path.insert(0,str(root/'src'))
from meta_analyse.http_client import ManagedAsyncClient
import httpx
async def main():
 accepted=asyncio.Event()
 async def peer(r,w):
  await r.read(1);accepted.set();w.close();await w.wait_closed()
 async with await asyncio.start_server(peer,'127.0.0.1',0) as s:
  events=[]
  async def trace(event,info):events.append(event)
  async with ManagedAsyncClient(verify=True,trust_env=False,timeout=2) as client:
   req=client.build_request('GET',f'https://127.0.0.1:{s.sockets[0].getsockname()[1]}/',extensions={'trace':trace})
   try:await client.send(req);raise AssertionError('unexpected success')
   except httpx.ConnectError as e:
    assert accepted.is_set();assert req.extensions['trace'] is trace
    print(json.dumps({'case':'handshake_abort','result':'ConnectError; caller trace restored','error':repr(e),'trace':events},indent=2))
  assert client.is_closed
asyncio.run(main())
