import asyncio
from decimal import Decimal as D
import pytest
from meta_analyse.desktop_service import DesktopService
from meta_analyse.runtime import Runtime

class Exchange:
    async def top_volatile(self, *args):
        raise OSError('offline secret=password')
    async def close(self):
        self.closed = True

class Api:
    async def close(self):
        self.closed = True

@pytest.mark.asyncio
async def test_offline_error_is_visible_and_credentials_are_not_exposed():
    api, exchange = Api(), Exchange()
    service = DesktopService(None, lambda snapshot: None)
    service.api, service.exchange = api, exchange
    service.runtime = Runtime(api, exchange)
    await service.refresh()
    snapshot = service.snapshot()
    assert 'OSError' in snapshot.status
    assert 'password' not in snapshot.status
    await service.close()
    assert api.closed and exchange.closed

@pytest.mark.asyncio
async def test_disconnect_during_metadata_prevents_late_session(monkeypatch):
    from meta_analyse import instruments
    entered = asyncio.Event()
    async def stalled(exchange):
        entered.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(instruments, 'instruments', stalled)
    service = DesktopService(object(), lambda snapshot: None)
    service.exchange = Exchange()
    service.connect_flow(['BTCUSDT'], D('100'))
    service.connect_flow(['BTCUSDT'], D('100'))
    await entered.wait()
    await service.disconnect_flow()
    assert service.snapshot().flow_state == 'disconnected'
    assert service.session is None
    assert service.flow_task is None
    await service.close()

@pytest.mark.asyncio
async def test_monitor_double_start_and_close_cancel_tasks():
    service = DesktopService(None, lambda snapshot: None)
    entered = asyncio.Event()
    class Monitor:
        running = False
        async def run(self):
            entered.set()
            await asyncio.Event().wait()
        def stop(self):
            self.running = False
    service.runtime = Monitor()
    await service.start_monitor()
    await service.start_monitor()
    await entered.wait()
    task = service.monitor_task
    await service.close()
    assert task.done()
@pytest.mark.asyncio
async def test_failed_collector_is_reported_and_other_tasks_are_drained():
    service = DesktopService(None, lambda snapshot: None)
    from meta_analyse.analysis_session import AnalysisSession
    s = AnalysisSession(None, None, {'BTCUSDT': D('.5')})
    async def fail():
        raise OSError('secret=hidden')
    task = asyncio.create_task(fail())
    sibling = asyncio.create_task(asyncio.Event().wait())
    s.raw.tasks.append(task)
    s.market.tasks.append(sibling)
    service.session, service.flow_state = s, 'connected'
    await asyncio.sleep(0)
    await service.check_health()
    assert service.snapshot().flow_state == 'failed'
    assert 'OSError' in service.snapshot().flow_status
    assert 'hidden' not in service.snapshot().flow_status
    assert sibling.done()
    await service.close()
@pytest.mark.asyncio
async def test_monitor_reports_offline_retries_without_exposing_error_text():
    from meta_analyse.runtime import Runtime
    statuses = []
    class Offline:
        async def discover(self):
            raise ConnectionError('password=hidden')
    runtime = Runtime(Offline(), None, on_status=statuses.append)
    task = asyncio.create_task(runtime.run())
    try:
        for _ in range(20):
            if statuses:
                break
            await asyncio.sleep(.01)
        assert statuses and 'ConnectionError' in statuses[-1]
        assert 'hidden' not in statuses[-1]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert not runtime.running
@pytest.mark.asyncio
async def test_duplicate_disconnect_keeps_stopping_until_cleanup_finishes():
    service = DesktopService(None, lambda snapshot: None)
    entered, release = asyncio.Event(), asyncio.Event()
    class Session:
        async def stop(self):
            entered.set()
            await release.wait()
    service.session = Session()
    service.flow_state = 'connected'
    first = asyncio.create_task(service.disconnect_flow())
    await entered.wait()
    second = asyncio.create_task(service.disconnect_flow())
    await asyncio.sleep(0)
    try:
        assert service.flow_state == 'stopping'
        assert not second.done()
        service.connect_flow(['BTCUSDT'], D('100'))
        assert service.flow_task is None
    finally:
        release.set()
        await asyncio.gather(first, second)
    assert service.flow_state == 'disconnected'
    await service.close()
