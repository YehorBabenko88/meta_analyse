import asyncio
import time
import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication
from meta_analyse.desktop import Window
from meta_analyse.exchange import BybitPublic

def pump(app, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(.01)
    assert predicate(), 'Qt state did not settle'

def test_close_during_startup_drains_worker_and_closes_loop(app, monkeypatch):
    async def stalled(self, *args):
        await asyncio.Event().wait()
    monkeypatch.setattr(BybitPublic, 'top_volatile', stalled)
    window = Window()
    window.show()
    window.close()
    # Completion is the invariant; Windows CI scheduling can exceed 250 ms.
    pump(app, lambda: not window.worker.is_alive() and not window.isVisible())
    assert window.loop.is_closed()
    assert not window.isVisible()

def test_offline_snapshot_is_rendered_on_qt_thread(app, monkeypatch):
    async def offline(self, *args):
        raise OSError('password=do-not-render')
    monkeypatch.setattr(BybitPublic, 'top_volatile', offline)
    window = Window()
    try:
        pump(app, lambda: 'OSError' in window.status.text())
        assert 'do-not-render' not in window.status.text()
        assert QThread.currentThread() == window.thread()
    finally:
        window.close()
        pump(app, lambda: not window.worker.is_alive() and not window.isVisible())
def test_close_while_flow_metadata_is_pending_cancels_connection(app, monkeypatch):
    import threading
    from meta_analyse import instruments
    entered = threading.Event()
    async def metadata(exchange):
        entered.set()
        await asyncio.Event().wait()
    async def watchlist(self, *args):
        return ['BTCUSDT']
    monkeypatch.setenv('META_ANALYSE_DSN', 'invalid dsn')
    monkeypatch.setattr(instruments, 'instruments', metadata)
    monkeypatch.setattr(BybitPublic, 'top_volatile', watchlist)
    window = Window()
    window.show()
    pump(app, lambda: window.list.count() == 1)
    window.list.item(0).setSelected(True)
    window.connect_flow()
    pump(app, entered.is_set)
    window.close()
    pump(app, lambda: not window.worker.is_alive() and not window.isVisible())
    assert window.service.session is None
    assert window.service.flow_task is None
    assert window.loop.is_closed()
def test_client_constructor_failure_is_visible_and_releases_partial_resources(app, monkeypatch):
    from meta_analyse.ports import MetaScalp
    clients = []
    original = MetaScalp.__init__
    def capture(self):
        original(self)
        clients.append(self.client)
    monkeypatch.setattr(MetaScalp, '__init__', capture)
    monkeypatch.setenv('SSL_CERT_FILE', str(__import__('pathlib').Path.cwd() / 'missing-audit-certificate.pem'))
    window = Window()
    window.show()
    try:
        pump(app, lambda: 'FileNotFoundError' in window.status.text())
        pump(app, lambda: not window.worker.is_alive())
        assert window.loop.is_closed()
        assert clients and clients[0].is_closed
        window.refresh()  # requests after worker failure must be rejected cleanly
        window.close()
        pump(app, lambda: not window.isVisible())
    finally:
        if not window.worker.is_alive() and not window.loop.is_closed():
            window.loop.close()
        window._closed = True
        window.close()
