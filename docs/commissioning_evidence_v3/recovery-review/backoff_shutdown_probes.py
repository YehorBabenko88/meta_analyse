import asyncio,time
from unittest.mock import patch
import meta_analyse.orderbook_stream as m
class Broken:
 async def __aenter__(self):raise OSError('offline')
 async def __aexit__(self,*a):pass
async def case(cancel):
 reached=asyncio.Event();stop=asyncio.Event()
 async def gap(s,r):
  if 'disconnected' in r:reached.set()
 stream=m.OrderBookStream(None,gap,backoff_base=30,backoff_max=60)
 with patch.object(m.websockets,'connect',lambda *a,**k:Broken()):
  t=asyncio.create_task(stream.run(['BTCUSDT'],stop));await reached.wait();await asyncio.sleep(.01)
  start=time.monotonic()
  if cancel:t.cancel()
  else:stop.set()
  try:await asyncio.wait_for(t,.3)
  except asyncio.CancelledError:assert cancel
  assert t.done()
  print('PASS',('cancellation' if cancel else 'stop'),'during active 30s backoff elapsed',round(time.monotonic()-start,4))
async def main():await case(False);await case(True)
asyncio.run(main())
