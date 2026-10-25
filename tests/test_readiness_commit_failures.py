"""Disk/connection failure witnesses through the real transport callback boundary."""
import asyncio
import errno
import pytest
import psycopg
from meta_analyse.market_collector import MarketCollector
from meta_analyse.orderbook_stream import OrderBookStream
from test_orderbook_autonomous_recovery import FakeSocket,packet


@pytest.mark.parametrize('phase',['execute','commit'])
@pytest.mark.parametrize('failure',['disk_full','connection_lost'])
@pytest.mark.asyncio
async def test_storage_fault_never_promotes_telemetry_or_snapshot(monkeypatch,phase,failure):
    error=OSError(errno.ENOSPC,'private fixture') if failure=='disk_full' else psycopg.OperationalError('private fixture')
    callbacks=[];gaps=[];stop=asyncio.Event()
    class Store:
        def connect(self):
            class Connection:
                def __enter__(self):return self
                def execute(self,*args):
                    if phase=='execute':raise error
                def __exit__(self,typ,*args):
                    if typ is None and phase=='commit':raise error
            return Connection()
    async def promoted(*args):callbacks.append(True)
    async def gap(*args):gaps.append(True);stop.set()
    collector=MarketCollector(Store(),None,on_book=promoted,on_gap=gap)
    socket=FakeSocket([packet('snapshot',1,1)])
    monkeypatch.setattr('meta_analyse.orderbook_stream.websockets.connect',lambda *a,**kw:socket)
    stream=OrderBookStream(collector._book,collector._gap,backoff_base=.001,backoff_max=.01)
    await asyncio.wait_for(stream.run(['BTCUSDT'],stop),1)
    assert callbacks==[] and gaps and not stream.books['BTCUSDT'].valid
    assert collector.telemetry.snapshot().events==()
    assert collector.telemetry.snapshot().gaps
    assert socket.closed
