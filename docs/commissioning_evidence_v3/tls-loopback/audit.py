import asyncio, ssl, subprocess, sys, pathlib, json, traceback
ROOT=pathlib.Path(r'C:/Users/LS-5/Documents/Codex/2026-10-15/github-https-github-com-yehorbabenko88-meta/work/windows-commissioning-audit')
OUT=pathlib.Path(__file__).parent
sys.path.insert(0,str(ROOT/'src'))
from meta_analyse.http_client import ManagedAsyncClient
import httpx
OPENSSL=r'C:/Program Files/Git/usr/bin/openssl.exe'
def openssl(*args):
 p=subprocess.run([OPENSSL,*args],cwd=OUT,text=True,capture_output=True)
 with (OUT/'openssl.log').open('a') as f:f.write(' '.join(args)+'\n'+p.stdout+p.stderr)
 p.check_returncode()
openssl('req','-x509','-newkey','rsa:2048','-nodes','-keyout','ca.key','-out','ca.pem','-days','2','-subj','/CN=TLS audit CA','-addext','basicConstraints=critical,CA:TRUE')
for name,host in [('good','localhost'),('wrong','wrong.invalid')]:
 openssl('req','-newkey','rsa:2048','-nodes','-keyout',name+'.key','-out',name+'.csr','-subj','/CN='+host)
 (OUT/(name+'.ext')).write_text('subjectAltName=DNS:'+host+'\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n')
 openssl('x509','-req','-in',name+'.csr','-CA','ca.pem','-CAkey','ca.key','-CAcreateserial','-out',name+'.pem','-days','2','-extfile',name+'.ext')
openssl('req','-x509','-newkey','rsa:2048','-nodes','-keyout','self.key','-out','self.pem','-days','2','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost')
results=[]
async def cert_case(name,verify,expected):
 ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(OUT/(name+'.pem'),OUT/(name+'.key'))
 async def peer(r,w):
  try:
   await r.readuntil(b'\r\n\r\n');w.write(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK');await w.drain()
  finally:w.close();await w.wait_closed()
 async with await asyncio.start_server(peer,'127.0.0.1',0,ssl=ctx) as server:
  port=server.sockets[0].getsockname()[1]
  async with ManagedAsyncClient(verify=verify,trust_env=False,timeout=2) as client:
   try:
    response=await client.get(f'https://localhost:{port}/');assert expected=='success';assert response.status_code==200 and response.text=='OK'
    results.append({'case':name,'result':'success','status':200,'check_hostname':verify.check_hostname,'verify_mode':int(verify.verify_mode)})
   except httpx.ConnectError as e:
    assert expected in str(e),repr(e)
    results.append({'case':name,'result':'rejected','error':str(e),'verify':True if verify is True else {'check_hostname':verify.check_hostname,'verify_mode':int(verify.verify_mode)}})
async def pending_case(mode):
 accepted=asyncio.Event();disconnected=asyncio.Event();writers=set();events=[]
 async def peer(r,w):
  writers.add(w)
  try:
   assert await r.read(1);accepted.set()
   while await r.read(65536):pass
  finally:
   w.close();await w.wait_closed();writers.discard(w);disconnected.set()
 async def trace(event,info):events.append(event)
 async with await asyncio.start_server(peer,'127.0.0.1',0) as server:
  port=server.sockets[0].getsockname()[1]
  client=ManagedAsyncClient(verify=True,trust_env=False,timeout=.3 if mode=='timeout' else 5)
  task=asyncio.create_task(client.get(f'https://127.0.0.1:{port}/',extensions={'trace':trace}))
  try:
   await asyncio.wait_for(accepted.wait(),2)
   if mode=='cancel':task.cancel()
   try:await task;raise AssertionError('unexpected success')
   except asyncio.CancelledError:assert mode=='cancel'
   except httpx.ConnectTimeout:assert mode=='timeout'
   await asyncio.wait_for(disconnected.wait(),2)
   await client.aclose();assert client.is_closed
   results.append({'case':mode,'result':'peer EOF observed; client closed','trace':events})
  finally:
   task.cancel();await asyncio.gather(task,return_exceptions=True);await client.aclose()
   for w in tuple(writers):w.close();await w.wait_closed()
async def main():
 trusted=ssl.create_default_context(cafile=str(OUT/'ca.pem'));assert trusted.check_hostname and trusted.verify_mode==ssl.CERT_REQUIRED
 await cert_case('self',True,'self-signed certificate')
 await cert_case('wrong',trusted,'Hostname mismatch')
 await cert_case('good',trusted,'success')
 await pending_case('timeout');await pending_case('cancel')
 print(json.dumps({'source':str(ROOT),'module':sys.modules['meta_analyse.http_client'].__file__,'python':sys.version,'httpx':httpx.__version__,'results':results},indent=2))
asyncio.run(main())
