"""Real Qt/worker/loopback WebSockets and disposable PostgreSQL stress checks."""
import asyncio
import json
import time
import httpx
import pytest
import pytest_asyncio
import websockets
from websockets.asyncio.server import serve
from meta_analyse.desktop import Window
from meta_analyse.exchange import BybitPublic
from meta_analyse.ports import MetaScalp
from test_windows_smoke import until

@pytest_asyncio.fixture
async def load_peers(monkeypatch):
    symbols = tuple(f'SYM{i:02d}USDT' for i in range(20))
    state = {'frames':0,'connections':0,'active':0,'errors':[],'http_writes':[],'topics':set()}
    def http(request):
        if request.method != 'GET':
            state['http_writes'].append(request.url.path)
            raise AssertionError('read-only test forbids HTTP writes')
        path = request.url.path
        if path.endswith('/tickers'):
            data = {'list':[{'symbol':s,'turnover24h':'2000000','lastPrice':'100','prevPrice24h':'90'} for s in symbols]}
        elif path.endswith('/instruments-info'):
            data = {'list':[{'symbol':s,'status':'Trading','launchTime':'1000','priceFilter':{'tickSize':'.5'}} for s in symbols]}
        elif path.endswith('/open-interest'):
            data = {'list':[{'timestamp':'60000','openInterest':'1000'}]}
        else:
            raise AssertionError(path)
        return httpx.Response(200,json={'retCode':0,'result':data})
    def exchange_init(self):
        self.client = httpx.AsyncClient(base_url='https://mock.exchange',transport=httpx.MockTransport(http))
    def api_init(self):
        self.base = None
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(http))
    monkeypatch.setattr(BybitPublic,'__init__',exchange_init)
    monkeypatch.setattr(MetaScalp,'__init__',api_init)
    async def socket(ws):
        state['connections'] += 1
        state['active'] += 1
        connection = state['connections']
        try:
            subscription = json.loads(await ws.recv())
            assert subscription['op'] == 'subscribe'
            topics = subscription['args']
            state['topics'].update(topics)
            frame = 0
            while True:
                frame += 1
                for topic in topics:
                    symbol = topic.rsplit('.',1)[-1]
                    if topic.startswith('publicTrade.'):
                        payload = {'topic':topic,'data':[{'s':symbol,'i':f'{connection}-{frame}-{symbol}',
                            'T':60000+frame,'p':'100','v':'2','S':'Buy'}]}
                    else:
                        payload = {'topic':topic,'type':'snapshot','ts':60000+frame,
                            'data':{'s':symbol,'u':frame,'seq':frame,'b':[['99','2']],'a':[['101','2']]}}
                    await ws.send(json.dumps(payload))
                    state['frames'] += 1
                await asyncio.sleep(.005)
        except websockets.ConnectionClosed:
            pass
        except Exception as exc:
            state['errors'].append(type(exc).__name__)
        finally:
            state['active'] -= 1
    original = websockets.connect
    async with serve(socket,'127.0.0.1',0) as server:
        port = server.sockets[0].getsockname()[1]
        def local(url,**kwargs):
            assert url.startswith('wss://stream.bybit.com/')
            return original(f'ws://127.0.0.1:{port}',**kwargs)
        monkeypatch.setattr(websockets,'connect',local)
        yield symbols,state

@pytest.mark.asyncio
async def test_twenty_connect_disconnect_cycles_drain_collectors(postgres_store,load_peers,monkeypatch,app):
    symbols,state = load_peers
    monkeypatch.setenv('META_ANALYSE_DSN',postgres_store.dsn)
    window = Window()
    window.show()
    try:
        await until(app,lambda: window.list.count()==20)
        # Different selected symbols across cycles also exercise row membership.
        for cycle in range(20):
            window.list.clearSelection()
            symbol = symbols[cycle]
            for i in range(window.list.count()):
                if window.list.item(i).text()==symbol:
                    window.list.item(i).setSelected(True)
            window.connect_flow()
            window.connect_flow()
            await until(app,lambda: window._snapshot.flow_state=='connected' and symbol in {r.symbol for r in window._snapshot.flow_rows})
            window.disconnect_flow()
            window.disconnect_flow()
            await until(app,lambda: window._snapshot.flow_state=='disconnected' and state['active']==0)
            async def inspect():
                service = window.service
                return service.session is None, service.flow_task is None, [t.get_coro().__qualname__ for t in asyncio.all_tasks()
                    if not t.done() and any(name in t.get_coro().__qualname__ for name in ('RawTradeStream','OrderBookStream','_oi_loop'))]
            future = window.schedule(inspect())
            await until(app,future.done)
            assert future.result()==(True,True,[])
            assert all(r.quality=='UNVERIFIED' for r in window._snapshot.flow_rows)
        assert not state['errors'] and not state['http_writes']
    finally:
        window.close()
        await until(app,lambda: not window.worker.is_alive() and not window.isVisible())
        assert window.loop.is_closed()

@pytest.mark.asyncio
@pytest.mark.parametrize('disconnect_first',[False,True])
async def test_close_with_twenty_active_instruments_and_pending_db_write(postgres_store,load_peers,monkeypatch,app,disconnect_first):
    import threading
    from meta_analyse.raw_store import RawStore
    symbols,state = load_peers
    entered,release = threading.Event(),threading.Event()
    stopping,release_stop = threading.Event(),threading.Event()
    original_save = RawStore.save
    def delayed_save(self,event):
        entered.set()
        if not release.wait(10):
            raise TimeoutError('test failed to release DB operation')
        return original_save(self,event)
    monkeypatch.setattr(RawStore,'save',delayed_save)
    monkeypatch.setenv('META_ANALYSE_DSN',postgres_store.dsn)
    window = Window()
    window.show()
    try:
        await until(app,lambda: window.list.count()==20)
        window.list.selectAll()
        window.connect_flow()
        expected = {f'{prefix}.{symbol}' for prefix in ('publicTrade','orderbook.50') for symbol in symbols}
        await until(app,lambda: entered.is_set() and window._snapshot.flow_state=='connected'
                    and state['active']==4 and expected <= state['topics'])
        if disconnect_first:
            async def install_stop_gate():
                session = window.service.session
                original_stop = session.stop
                async def gated_stop():
                    stopping.set()
                    await original_stop()
                    # Hold ownership of cleanup even if Linux closes sockets
                    # before the next 100ms GUI snapshot observes stopping.
                    while not release_stop.is_set():
                        await asyncio.sleep(.001)
                session.stop = gated_stop
            configured = window.schedule(install_stop_gate())
            await until(app,configured.done)
            configured.result()
            window.disconnect_flow()
            await until(app,stopping.is_set)
        before = time.perf_counter()
        window.close()
        assert time.perf_counter()-before < .25
        # Keep the DB operation outstanding and prove Qt continues to dispatch.
        ticks = []
        from PySide6.QtCore import QTimer
        timer = QTimer()
        timer.setInterval(5)
        timer.timeout.connect(lambda: ticks.append(time.perf_counter()))
        timer.start()
        await until(app,lambda: len(ticks)>=5)
        timer.stop()
        assert window.worker.is_alive()
        release.set()
        release_stop.set()
        await until(app,lambda: not window.worker.is_alive() and not window.isVisible())
        assert window.loop.is_closed()
        assert window.service.api.client.is_closed and window.service.exchange.client.is_closed
        assert not state['http_writes']
    finally:
        release.set()
        release_stop.set()
        window.close()
        await until(app,lambda: not window.worker.is_alive())
