"""Offline worker/UI health refusal witnesses; no Qt display or network."""
import asyncio
from types import SimpleNamespace
import pytest
from meta_analyse.desktop_service import DesktopService
from meta_analyse.feed_watchdog import FeedWatchdog


@pytest.mark.parametrize('late',[False,True])
@pytest.mark.asyncio
async def test_disconnect_invalidates_before_drain_and_ignores_late_frames(late):
    service=DesktopService(None,lambda snapshot:None)
    entered,release=asyncio.Event(),asyncio.Event()
    class Session:
        async def stop(self):entered.set();await release.wait()
    service.session=Session();service.flow_state='connected'
    footprint=dict(poc='100',delta='1',trusted=True)
    tape=SimpleNamespace(trades_per_second=1,trusted=True)
    await service._flow_execution('BTCUSDT',footprint,tape)
    await service._flow_book('BTCUSDT',None)
    assert service.bridge.snapshot()[0].quality=='PROVISIONAL'
    task=asyncio.create_task(service.disconnect_flow())
    try:
        await asyncio.wait_for(entered.wait(),1)
        if late:
            await service._flow_execution('BTCUSDT',footprint,tape)
            await service._flow_book('BTCUSDT',None)
        assert service.flow_state=='stopping'
        assert service.bridge.snapshot()[0].quality=='UNVERIFIED'
    finally:
        release.set();await task;await service.close()


@pytest.mark.parametrize('threshold',[float('nan'),float('inf'),True,'8',None])
def test_malformed_stale_threshold_never_creates_permanently_fresh_feed(threshold):
    with pytest.raises(ValueError):FeedWatchdog(threshold)


def test_positive_finite_stale_threshold_control(monkeypatch):
    now=[10.0];monkeypatch.setattr('meta_analyse.feed_watchdog.monotonic',lambda:now[0])
    health=FeedWatchdog(2.5);health.observed('BTCUSDT');now[0]=13
    assert health.inspect(['BTCUSDT'])[0].status=='STALE'
