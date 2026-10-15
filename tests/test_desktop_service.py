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

@pytest.mark.asyncio
async def test_collector_crash_invalidates_telemetry_and_allows_reconnect():
    """A dead sibling must never leave old persisted counters visible."""
    from meta_analyse.analysis_session import AnalysisSession
    from meta_analyse.market_telemetry import MarketTelemetry
    from types import SimpleNamespace
    service = DesktopService(None, lambda snapshot: None)
    service.runtime = SimpleNamespace(
        symbols=[], paper=SimpleNamespace(fills=[], positions={}), stop=lambda: None)
    session = AnalysisSession(None, None, {'BTCUSDT': D('.5')})
    session.market.telemetry.observe("orderbook", "BTCUSDT")
    session.market.telemetry.gap("orderbook", "BTCUSDT")
    async def fail():
        raise OSError("password=should-never-leak")
    crashed = asyncio.create_task(fail())
    sibling = asyncio.create_task(asyncio.Event().wait())
    session.raw.tasks.append(crashed)
    session.market.tasks.append(sibling)
    service.session, service.flow_state = session, "connected"
    await asyncio.sleep(0)
    assert service.snapshot().market_events == (("orderbook:BTCUSDT", 1),)
    await service.check_health()
    snapshot = service.snapshot()
    assert snapshot.flow_state == "failed"
    assert "OSError" in snapshot.flow_status
    assert "password" not in snapshot.flow_status
    assert snapshot.market_events == ()
    assert snapshot.market_gaps == ()
    assert snapshot.market_ages == ()
    assert sibling.done()
    assert service.session is None
    # A new session's diagnostics are independent of the failed collector.
    replacement = MarketTelemetry()
    replacement.observe("orderbook", "ETHUSDT")
    service.session = SimpleNamespace(market=SimpleNamespace(telemetry=replacement))
    service.flow_state = "connected"
    assert service.snapshot().market_events == (("orderbook:ETHUSDT", 1),)
    service.session = None
    service.flow_state = "disconnected"
    await service.close()

@pytest.mark.asyncio
async def test_reconnect_rejected_while_disconnect_task_is_pending_even_if_state_failed():
    """An old cleanup must never erase a newly created session."""
    service = DesktopService(None, lambda snapshot: None)
    entered, release = asyncio.Event(), asyncio.Event()
    class Session:
        async def stop(self):
            entered.set()
            await release.wait()
    old_session = Session()
    service.session = old_session
    service.flow_state = "connected"
    disconnect = asyncio.create_task(service.disconnect_flow())
    await entered.wait()
    try:
        # A competing health callback can change the visible state while
        # the disconnect task is still draining the previous session.
        service.flow_state = "failed"
        service.connect_flow(["BTCUSDT"], D("100"))
        assert service.flow_task is None
        assert service.session is old_session
    finally:
        release.set()
        await disconnect
    assert service.session is None
    assert service.flow_state == "disconnected"
    await service.close()

@pytest.mark.asyncio
async def test_idle_disconnect_is_idempotent_and_does_not_replace_cleanup_task():
    service = DesktopService(None, lambda snapshot: None)
    assert service.flow_state == "disconnected"
    assert service.disconnect_task is None
    await service.disconnect_flow()
    await service.disconnect_flow()
    assert service.disconnect_task is None
    assert service.flow_state == "disconnected"
    # An idle disconnect must not interfere with a later startup.
    service.flow_state = "connecting"
    async def pending():
        await asyncio.Event().wait()
    service.flow_task = asyncio.create_task(pending())
    await asyncio.sleep(0)
    await service.disconnect_flow()
    assert service.flow_task is None
    assert service.flow_state == "disconnected"
    await service.close()
