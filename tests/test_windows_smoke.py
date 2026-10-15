import asyncio
import json
import threading
import time
import httpx
import pytest
import websockets
from websockets.asyncio.server import serve
from PySide6.QtWidgets import QApplication
from meta_analyse.desktop import Window
from meta_analyse.exchange import BybitPublic
from meta_analyse.ports import MetaScalp
from meta_analyse.storage import Store

async def until(app, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        await asyncio.sleep(.01)
    assert predicate(), 'smoke state did not settle'

@pytest.mark.asyncio
async def test_windows_qt_mock_network_postgres_disconnect_restart(postgres_store, monkeypatch):
    app = QApplication.instance() or QApplication([])
    http_calls, ws_calls = [], []
    def http(request):
        http_calls.append((request.method, request.url.path))
        assert request.method == 'GET', 'smoke test forbids all HTTP writes'
        path = request.url.path
        if path == '/ping':
            return httpx.Response(200, json={'name': 'MetaScalp mock'})
        if path == '/api/connections':
            return httpx.Response(200, json=[{'exchange': 'Bybit', 'state': 2, 'id': 1}])
        if path == '/v5/market/tickers':
            data = {'list': [{'symbol':'BTCUSDT','turnover24h':'2000000','lastPrice':'100','prevPrice24h':'90'}]}
        elif path == '/v5/market/instruments-info':
            data = {'list':[{'symbol':'BTCUSDT','status':'Trading','launchTime':'1000','priceFilter':{'tickSize':'.5'}}]}
        elif path == '/v5/market/open-interest':
            data = {'list':[{'timestamp':'60000','openInterest':'1000'}]}
        else:
            raise AssertionError(f'unexpected HTTP endpoint: {path}')
        return httpx.Response(200, json={'retCode':0,'result':data})
    def exchange_init(self):
        self.client = httpx.AsyncClient(base_url='https://mock.exchange', transport=httpx.MockTransport(http))
    def api_init(self):
        self.base = None
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(http))
    monkeypatch.setattr(BybitPublic, '__init__', exchange_init)
    monkeypatch.setattr(MetaScalp, '__init__', api_init)
    counter = {'trade':0, 'book':0, 'terminal':0}
    async def socket(ws):
        first = json.loads(await ws.recv())
        ws_calls.append(first)
        if first.get('Type') == 'trade_subscribe':
            counter['terminal'] += 1
            await ws.send(json.dumps({'Type':'trade_update','Data':{'ticker':'BTCUSDT','trades':[
                {'time':'2026-10-15T10:00:00Z','price':'100','size':'2','side':'Buy'}]}}))
            await ws.wait_closed()
            return
        args = first['args']
        assert first['op'] == 'subscribe'
        if args == ['publicTrade.BTCUSDT']:
            counter['trade'] += 1
            await ws.send(json.dumps({'topic':'publicTrade.BTCUSDT','data':[
                {'s':'BTCUSDT','i':str(counter['trade']),'T':60000+counter['trade'],
                 'p':'100','v':'2','S':'Buy'}]}))
            # A real WebSocket close must invalidate quality and reconnect.
            if counter['trade'] == 1:
                await asyncio.sleep(.1)
                await ws.close()
                return
        elif args == ['orderbook.50.BTCUSDT']:
            counter['book'] += 1
            await ws.send(json.dumps({'topic':'orderbook.50.BTCUSDT','type':'snapshot','ts':60000,
                'data':{'s':'BTCUSDT','u':counter['book'],'seq':counter['book'],
                        'b':[['99','2']],'a':[['101','2']]}}))
        else:
            raise AssertionError(f'unexpected subscription: {first}')
        await ws.wait_closed()
    original_connect = websockets.connect
    async with serve(socket, '127.0.0.1', 0) as server:
        port = server.sockets[0].getsockname()[1]
        def local_connect(url, **kwargs):
            assert url.startswith(('wss://stream.bybit.com/', 'ws://127.0.0.1:'))
            return original_connect(f'ws://127.0.0.1:{port}', **kwargs)
        monkeypatch.setattr(websockets, 'connect', local_connect)
        monkeypatch.setenv('META_ANALYSE_DSN', postgres_store.dsn)
        window = Window()
        window.show()
        try:
            await until(app, lambda: window.list.count() == 1)
            window.list.item(0).setSelected(True)
            window.level_price.setValue(100)
            window.connect_flow()
            window.connect_flow()  # duplicate requests must be harmless
            window.start()
            window.start()
            await until(app, lambda: counter['trade'] >= 2 and window.flow_table.rowCount() == 1)
            with postgres_store.connect() as conn:
                assert conn.execute('SELECT count(*) FROM meta_analyse.executions').fetchone()[0] >= 1
                assert conn.execute('SELECT count(*) FROM meta_analyse.orderbook_observations').fetchone()[0] >= 1
                assert conn.execute('SELECT count(*) FROM meta_analyse.data_gaps').fetchone()[0] >= 2
            assert 'NOT verified' in window.flow_status.text()
            assert window.flow_table.item(0, 5).text() == 'UNVERIFIED'
            window.disconnect_flow()
            await until(app, lambda: window._snapshot.flow_state == 'disconnected')
            assert window.flow_table.item(0, 5).text() == 'UNVERIFIED'
            window.connect_flow()
            await until(app, lambda: counter['trade'] >= 3 and window._snapshot.flow_state == 'connected')
            def persisted_restart():
                with postgres_store.connect() as conn:
                    return (conn.execute('SELECT count(*) FROM meta_analyse.executions').fetchone()[0] >= 3
                            and conn.execute('SELECT count(*) FROM meta_analyse.orderbook_observations').fetchone()[0] >= 2
                            and conn.execute('SELECT count(*) FROM meta_analyse.open_interest_samples').fetchone()[0] >= 1)
            await until(app, persisted_restart)
            assert counter['terminal'] == 1, window._snapshot.status
            assert all(method == 'GET' for method, _ in http_calls)
        finally:
            before = time.monotonic()
            window.close()
            assert time.monotonic() - before < .25
            await until(app, lambda: not window.worker.is_alive() and not window.isVisible())
            app.processEvents()
            assert window.loop.is_closed()
            assert window.service.api.client.is_closed
            assert window.service.exchange.client.is_closed
            assert not window.isVisible()

@pytest.mark.asyncio
async def test_invalid_dsn_fails_without_started_session():
    from decimal import Decimal
    from meta_analyse.analysis_session import AnalysisSession
    session = AnalysisSession(Store('invalid dsn'), None, {'BTCUSDT':Decimal('.5')})
    with pytest.raises(Exception):
        await session.start()
    assert not session.started
    assert not session.raw.tasks and not session.market.tasks
    await session.stop()
def test_database_operations_have_bounded_timeouts(postgres_store):
    with postgres_store.connect() as conn:
        assert conn.execute('SHOW statement_timeout').fetchone()[0] == '5s'
        assert conn.execute('SHOW lock_timeout').fetchone()[0] == '5s'
