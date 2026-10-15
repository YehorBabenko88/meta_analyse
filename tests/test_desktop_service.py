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

@pytest.mark.asyncio
async def test_close_drains_monitor_and_clients_if_runtime_stop_raises():
    """Shutdown failures must not skip unrelated resource cleanup."""
    service = DesktopService(None, lambda snapshot: None)
    events = []
    class BadRuntime:
        def stop(self):
            events.append("runtime-stop")
            raise RuntimeError("password=do-not-show")
    class Client:
        def __init__(self, name):
            self.name = name
        async def close(self):
            events.append(self.name)
    async def monitor():
        try:
            await asyncio.Event().wait()
        finally:
            events.append("monitor-drained")
    service.runtime = BadRuntime()
    service.api, service.exchange = Client("api-closed"), Client("exchange-closed")
    service.monitor_task = asyncio.create_task(monitor())
    await asyncio.sleep(0)
    await service.close()
    assert events == ["runtime-stop", "monitor-drained", "api-closed", "exchange-closed"]
    assert service.monitor_task.done()
    assert "RuntimeError" in service.status
    assert "password" not in service.status

@pytest.mark.asyncio
async def test_close_releases_clients_when_session_stop_fails():
    """A collector teardown exception must not prevent API client closure."""
    service = DesktopService(None, lambda snapshot: None)
    events = []
    class Session:
        async def stop(self):
            events.append("session-stop")
            raise RuntimeError("token=private")
    class Client:
        def __init__(self, name):
            self.name = name
        async def close(self):
            events.append(self.name)
    service.session = Session()
    service.flow_state = "connected"
    service.api, service.exchange = Client("api-close"), Client("exchange-close")
    await service.close()
    assert events == ["session-stop", "api-close", "exchange-close"]
    assert service.flow_state == "disconnected"
    assert service.session is None
    assert "token=private" not in service.status
    assert "RuntimeError" in service.status

@pytest.mark.asyncio
async def test_multiple_collector_failures_report_one_and_drain_all_tasks():
    """Simultaneous worker crashes should yield one failed state, no leaked tasks."""
    from meta_analyse.analysis_session import AnalysisSession
    service = DesktopService(None, lambda snapshot: None)
    session = AnalysisSession(None, None, {'BTCUSDT': D('.5')})
    async def fail(message):
        raise OSError(message)
    first = asyncio.create_task(fail("password=first"))
    second = asyncio.create_task(fail("token=second"))
    pending = asyncio.create_task(asyncio.Event().wait())
    session.raw.tasks.extend([first, pending])
    session.market.tasks.append(second)
    service.session, service.flow_state = session, "connected"
    await asyncio.sleep(0)
    await service.check_health()
    assert service.flow_state == "failed"
    assert "OSError" in service.flow_status
    assert "password" not in service.flow_status
    assert "token" not in service.flow_status
    assert service.session is None
    assert first.done() and second.done() and pending.done()
    await service.check_health()
    assert service.flow_state == "failed"
    await service.close()

@pytest.mark.asyncio
@pytest.mark.parametrize("mode,expected", [
    ("normal", "NoneType"),
    ("cancelled", "CancelledError"),
])
async def test_collector_normal_exit_or_cancellation_marks_feed_failed(mode, expected):
    """A collector ending without an exception is not a healthy running feed."""
    from meta_analyse.analysis_session import AnalysisSession
    service = DesktopService(None, lambda snapshot: None)
    session = AnalysisSession(None, None, {'BTCUSDT': D('.5')})
    async def normal():
        return None
    async def waiting():
        await asyncio.Event().wait()
    ended = asyncio.create_task(normal() if mode == "normal" else waiting())
    sibling = asyncio.create_task(waiting())
    session.raw.tasks.append(ended)
    session.market.tasks.append(sibling)
    service.session, service.flow_state = session, "connected"
    await asyncio.sleep(0)
    if mode == "cancelled":
        ended.cancel()
        await asyncio.gather(ended, return_exceptions=True)
    await service.check_health()
    assert service.flow_state == "failed"
    assert expected in service.flow_status
    assert service.session is None
    assert sibling.done()
    await service.close()

@pytest.mark.asyncio
async def test_close_during_collector_failure_does_not_restore_failed_state():
    """An in-flight health check must not override final shutdown status."""
    service = DesktopService(None, lambda snapshot: None)
    entered, release = asyncio.Event(), asyncio.Event()
    class Session:
        def __init__(self):
            async def failed():
                raise RuntimeError("collector failed")
            self.raw = type("Raw", (), {"tasks": [asyncio.create_task(failed())]})()
            self.market = type("Market", (), {"tasks": []})()
        async def stop(self):
            entered.set()
            await release.wait()
    service.session = Session()
    service.flow_state = "connected"
    await asyncio.sleep(0)
    health = asyncio.create_task(service.check_health())
    await entered.wait()
    closing = asyncio.create_task(service.close())
    await asyncio.sleep(0)
    assert service.closing
    release.set()
    await asyncio.gather(health, closing)
    assert service.flow_state == "disconnected"
    assert service.flow_status.startswith("Disconnected")
    assert service.session is None

@pytest.mark.asyncio
async def test_manual_disconnect_owns_cleanup_before_health_failure_reporting():
    """A completed worker must not override an already-started manual stop."""
    service = DesktopService(None, lambda snapshot: None)
    entered, release = asyncio.Event(), asyncio.Event()
    class Session:
        def __init__(self):
            async def failed():
                raise RuntimeError("collector crashed")
            self.raw = type("Raw", (), {"tasks": [asyncio.create_task(failed())]})()
            self.market = type("Market", (), {"tasks": []})()
        async def stop(self):
            entered.set()
            await release.wait()
    service.session = Session()
    service.flow_state = "connected"
    await asyncio.sleep(0)
    manual = asyncio.create_task(service.disconnect_flow())
    await entered.wait()
    await service.check_health()
    release.set()
    await manual
    assert service.flow_state == "disconnected"
    assert service.flow_status.startswith("Disconnected")
    assert service.session is None
    await service.close()

@pytest.mark.asyncio
async def test_health_failure_does_not_overwrite_new_connection_after_cleanup():
    """A reconnect between cleanup completion and health reporting wins."""
    service = DesktopService(None, lambda snapshot: None)
    async def failed():
        raise RuntimeError("collector stopped")
    ended = asyncio.create_task(failed())
    session = type("Session", (), {})()
    session.raw = type("Raw", (), {"tasks": [ended]})()
    session.market = type("Market", (), {"tasks": []})()
    service.session, service.flow_state = session, "connected"
    await asyncio.sleep(0)
    async def cleanup_then_reconnect():
        service.session = None
        service.flow_state = "connecting"
    service.disconnect_flow = cleanup_then_reconnect
    await service.check_health()
    assert service.flow_state == "connecting"
    assert service.flow_status != "Collector stopped (RuntimeError); data UNVERIFIED"
