import asyncio
import threading
import pytest
from meta_analyse.market_collector import MarketCollector

@pytest.mark.asyncio
async def test_collector_stop_retains_pending_database_write(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    writes = []
    collector = MarketCollector(None, None)
    def write(*args):
        entered.set()
        if not release.wait(5):
            raise TimeoutError('audit failed to release write')
        writes.append('committed')
    monkeypatch.setattr(collector.db, 'book', write)
    writing = asyncio.create_task(collector._book('BTCUSDT', object(), 1))
    assert await asyncio.to_thread(entered.wait, 2)
    collector.tasks = [writing]
    stopping = asyncio.create_task(collector.stop())
    try:
        for _ in range(20):
            await asyncio.sleep(0)
        assert not stopping.done(), 'stop acknowledged while a synchronous DB write remained active'
        assert not writes
    finally:
        release.set()
        await asyncio.gather(stopping, writing, return_exceptions=True)
    assert writes == ['committed']

@pytest.mark.parametrize('operation', ['import', 'audit'])
@pytest.mark.parametrize('timestamp', ['1e-999999999', '0e999999999', '-0e999999999'])
def test_extreme_decimal_validation_finishes_in_bounded_subprocess(operation, timestamp, tmp_path):
    import os
    from pathlib import Path
    import subprocess
    import sys
    code = '''
from meta_analyse.archive_db_import import parse_trade
from meta_analyse.bybit_archive_audit import audit_trade_gzip
import csv,gzip,sys
row=dict(trdMatchID='tiny',timestamp=sys.argv[3],price='1',size='1',side='Buy')
if sys.argv[1]=='import':
 assert parse_trade(row)[1].year==1970
else:
 with gzip.open(sys.argv[2],'wt',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
 result=audit_trade_gzip(sys.argv[2]);assert result.valid and result.first_ms==0
'''
    result = subprocess.run([sys.executable, '-c', code, operation, str(tmp_path/'tiny.gz'), timestamp],
        env=dict(os.environ, PYTHONPATH=str(Path('src').resolve())), capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
@pytest.mark.parametrize('first_delta', [(1, 1), (15, 26)])
async def test_orderbook_transport_reconnect_requires_fresh_snapshot(monkeypatch, first_delta):
    import json
    from decimal import Decimal
    from types import SimpleNamespace
    from meta_analyse import orderbook_stream as module
    def frame(kind, uid, seq, bid, ask):
        return dict(topic='orderbook.50.BTCUSDT', type=kind, ts=1,
                    data=dict(s='BTCUSDT',u=uid,seq=seq,b=[[str(bid),'2']],a=[[str(ask),'2']]))
    frames = [
        [frame('snapshot',10,20,100,102),frame('delta',14,25,101,102),ConnectionError('audit disconnect')],
        [frame('delta',*first_delta,10,12),frame('snapshot',20,100,10,12),frame('delta',23,105,11,12)],
    ]
    connections=[]
    class Socket:
        def __init__(self, values): self.values=iter(values)
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return False
        async def send(self, text): assert json.loads(text)['op']=='subscribe'
        async def recv(self):
            value=next(self.values)
            if isinstance(value,Exception): raise value
            return json.dumps(value)
    def connect(*args,**kwargs):
        index=len(connections);connections.append(index)
        return Socket(frames[index])
    original_sleep=asyncio.sleep
    async def virtual_backoff(seconds): await original_sleep(0)
    monkeypatch.setattr(module.websockets,'connect',connect)
    monkeypatch.setattr(module,'asyncio',SimpleNamespace(wait_for=asyncio.wait_for,sleep=virtual_backoff,
        TimeoutError=asyncio.TimeoutError,CancelledError=asyncio.CancelledError))
    stop=asyncio.Event(); observed=[]; gaps=[]
    async def book(symbol,state,ts):
        observed.append((state.update_id,dict(state.bids)))
        if state.update_id==23: stop.set()
    async def gap(symbols,reason): gaps.append(reason)
    stream=module.OrderBookStream(book,gap)
    await asyncio.wait_for(stream.run(['BTCUSDT'],stop),2)
    assert len(connections)==2
    assert [uid for uid,_ in observed]==[10,14,20,23]
    assert Decimal(100) not in observed[-1][1] and Decimal(101) not in observed[-1][1]
    assert stream.books['BTCUSDT'].valid and len(gaps)>=3


@pytest.mark.asyncio
async def test_public_rest_context_requires_certificate_and_hostname_verification():
    import ssl
    from meta_analyse.exchange import BybitPublic
    exchange=BybitPublic()
    try:
        context=exchange.client._transport._pool._ssl_context
        assert context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname
    finally:
        await exchange.close()


def test_required_postgres_gate_includes_contention_case():
    from pathlib import Path
    import runpy
    manifest=runpy.run_path(str(Path('scripts/check_integration_postgres.py')))
    assert 'test_contended_advisory_lock_fails_without_partial_import' in manifest['REQUIRED']
    assert len(manifest['REQUIRED'])==10

@pytest.mark.asyncio
async def test_service_close_waits_for_monitor_schema_write():
    from meta_analyse.desktop_service import DesktopService
    entered,release=threading.Event(),threading.Event()
    class Store:
        def initialize(self):
            entered.set()
            if not release.wait(5): raise TimeoutError('audit did not release schema write')
    class Runtime:
        def stop(self): pass
        async def run(self): pytest.fail('cancelled initialization must not start monitor')
    service=DesktopService(Store(),lambda _:None);service.runtime=Runtime()
    await service.start_monitor()
    assert await asyncio.to_thread(entered.wait,2)
    closing=asyncio.create_task(service.close())
    try:
        for _ in range(20): await asyncio.sleep(0)
        assert not closing.done(), 'service close acknowledged before schema write completed'
    finally:
        release.set()
        await closing

@pytest.mark.asyncio
async def test_commissioning_launcher_blocks_http_writes_before_transport(monkeypatch):
    import sys
    from pathlib import Path
    import httpx
    from meta_analyse.http_client import ManagedAsyncClient
    monkeypatch.syspath_prepend(str(Path('commissioning').resolve()))
    import run_readonly
    monkeypatch.setattr(ManagedAsyncClient,'send',ManagedAsyncClient.send)
    run_readonly.install_http_read_guard()
    calls=[]
    async def handler(request):
        calls.append(request.method)
        return httpx.Response(200,json={'ok':True})
    async with ManagedAsyncClient(transport=httpx.MockTransport(handler)) as client:
        for method in ('POST','PUT','PATCH','DELETE'):
            with pytest.raises(PermissionError): await client.request(method,'http://127.0.0.1/forbidden')
        assert not calls
        assert (await client.get('http://127.0.0.1/read')).is_success
    assert calls==['GET']

@pytest.mark.parametrize('configuration', ['dsn_address','environment_address','service'])
def test_commissioning_rejects_hidden_remote_database_routing(monkeypatch, configuration):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path('commissioning').resolve()))
    import preflight
    monkeypatch.delenv('PGHOSTADDR',raising=False)
    monkeypatch.delenv('PGSERVICE',raising=False)
    monkeypatch.delenv('PGSERVICEFILE',raising=False)
    dsn='host=127.0.0.1 dbname=meta_commission_test'
    if configuration=='dsn_address': dsn+=' hostaddr=198.51.100.8'
    if configuration=='environment_address': monkeypatch.setenv('PGHOSTADDR','198.51.100.8')
    if configuration=='service': monkeypatch.setenv('PGSERVICE','unexpected')
    with pytest.raises(ValueError): preflight.validate_local_database(dsn)


def test_commissioning_refuses_an_installed_package_from_another_checkout(monkeypatch,tmp_path):
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    monkeypatch.syspath_prepend(str(Path('commissioning').resolve()))
    import preflight
    monkeypatch.setitem(sys.modules,'meta_analyse',SimpleNamespace(__file__=str(tmp_path/'different'/'__init__.py')))
    with pytest.raises(ValueError): preflight.verify_package_source(tmp_path/'candidate')
