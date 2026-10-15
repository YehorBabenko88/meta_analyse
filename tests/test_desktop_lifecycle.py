import asyncio
import time
import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication
from meta_analyse.desktop import Window
from meta_analyse.exchange import BybitPublic

@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])

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
    before = time.monotonic()
    window.close()
    assert time.monotonic() - before < .25
    pump(app, lambda: not window.worker.is_alive())
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
        pump(app, lambda: not window.worker.is_alive())
