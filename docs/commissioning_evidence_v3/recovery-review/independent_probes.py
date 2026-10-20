import asyncio,json,sys
from decimal import Decimal
from unittest.mock import patch
import meta_analyse.orderbook_stream as m
print('SOURCE',m.__file__)
def p(kind='snapshot',u=1,seq=1,size='1',symbol='BTCUSDT',ts=1):
 return json.dumps(dict(topic='orderbook.50.'+symbol,type=kind,ts=ts,data=dict(s=symbol,u=u,seq=seq,b=[['100',size]],a=[['101','1']])))
class Sock:
 def __init__(self,messages=(),busy=None):self.msg=list(messages);self.busy=busy;self.closed=False
 async def __aenter__(self):return self
 async def __aexit__(self,*a):self.closed=True
 async def send(self,*a):pass
 async def recv(self):
  if self.msg:return self.msg.pop(0)
  if self.busy:
   await asyncio.sleep(.001);return self.busy
  await asyncio.Event().wait()
async def recovery(name,fault):
 first=Sock([p(),fault,p('delta',3,3)]);second=Sock([p(u=10,seq=10)])
 sockets=[first,second];stop=asyncio.Event();seen=[];gaps=[]
 async def book(s,b,t):
  seen.append(b)
  if len(seen)==2:stop.set()
 async def gap(s,r):gaps.append(r)
 stream=m.OrderBookStream(book,gap,silence_timeout=.02,backoff_base=.001,backoff_max=.004)
 with patch.object(m.websockets,'connect',lambda *a,**k:sockets.pop(0)):
  await asyncio.wait_for(stream.run(['BTCUSDT'],stop),.5)
 assert [b.update_id for b in seen]==[1,10] and first.closed and second.closed
 assert seen[0].valid and seen[0].bids[Decimal(100)]==1
 try:seen[0].bids[Decimal(100)]=2
 except TypeError:pass
 else:raise AssertionError('mutable snapshot')
 print('PASS',name,'epochs',stream.connection_epoch,'published',[b.update_id for b in seen], 'retained immutable')
async def silence(name,busy=None):
 first=Sock([p()],busy=busy);second=Sock([p(u=10,seq=10)]);sockets=[first,second];stop=asyncio.Event();seen=[]
 async def book(s,b,t):
  seen.append(b.update_id)
  if len(seen)==2:stop.set()
 async def gap(*a):pass
 stream=m.OrderBookStream(book,gap,silence_timeout=.015,backoff_base=.001,backoff_max=.004)
 with patch.object(m.websockets,'connect',lambda *a,**k:sockets.pop(0)):
  await asyncio.wait_for(stream.run(['BTCUSDT'],stop),.5)
 assert seen==[1,10] and first.closed
 print('PASS',name,'epochs',stream.connection_epoch)
async def cancel():
 ready=asyncio.Event();stop=asyncio.Event();sock=Sock([p()]);gaps=[]
 async def book(*a):ready.set()
 async def gap(s,r):gaps.append(r)
 stream=m.OrderBookStream(book,gap)
 with patch.object(m.websockets,'connect',lambda *a,**k:sock):
  t=asyncio.create_task(stream.run(['BTCUSDT'],stop));await ready.wait();await asyncio.sleep(0);t.cancel()
  try:await t
  except asyncio.CancelledError:pass
 assert sock.closed
 print('OBSERVATION cancellation closes socket but internal_valid=',stream.books['BTCUSDT'].valid,'gap_count=',len(gaps))
async def skip():
 stop=asyncio.Event();seen=[];sock=Sock([p(),p('delta',9,9)])
 async def book(s,b,t):
  seen.append(b.update_id)
  if len(seen)==2:stop.set()
 async def gap(*a):pass
 stream=m.OrderBookStream(book,gap)
 with patch.object(m.websockets,'connect',lambda *a,**k:sock):await stream.run(['BTCUSDT'],stop)
 assert seen==[1,9]
 print('PASS numeric sequence jumps permitted by documented strictly increasing Bybit rule',seen)
async def backoff():
 class Broken(Sock):
  async def __aenter__(self):raise OSError('offline')
 class Stop:
  count=0
  def is_set(self):return self.count>=5
  async def wait(self):self.count+=1;raise asyncio.TimeoutError
 stop=Stop();delays=[];original=asyncio.wait_for
 async def measured(aw,timeout):delays.append(timeout);return await original(aw,timeout)
 async def gap(*a):pass
 with patch.object(m.websockets,'connect',lambda *a,**k:Broken()),patch.object(m.random,'uniform',lambda *a:1),patch.object(m.asyncio,'wait_for',measured):
  await m.OrderBookStream(None,gap,backoff_base=.1,backoff_max=.4).run(['BTCUSDT'],stop)
 assert delays==[.1,.2,.4,.4,.4]
 print('PASS bounded exponential backoff',delays)
async def main():
 await recovery('invalid delta',p('delta',2,2,'NaN'))
 await recovery('sequence regression',p('delta',2,1))
 await recovery('update-id regression',p('delta',1,2))
 await silence('silent established feed')
 await silence('busy unrelated socket',json.dumps({'topic':'publicTrade.BTCUSDT','data':[]}))
 await skip();await backoff();await cancel()
asyncio.run(main())
