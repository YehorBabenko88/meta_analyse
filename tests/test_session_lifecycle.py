import asyncio
from decimal import Decimal as D
import pytest
from meta_analyse.analysis_session import AnalysisSession

@pytest.mark.parametrize('tick', ['0', '-1', 'NaN', 'Infinity'])
def test_invalid_tick_rejected_before_resources(tick):
    with pytest.raises(ValueError):
        AnalysisSession(None, None, {'BTCUSDT': D(tick)})

class Collector:
    def __init__(self, gate=None, fail_start=False, fail_stop=False):
        self.gate, self.fail_start, self.fail_stop = gate, fail_start, fail_stop
        self.tasks = []
        self.entered = asyncio.Event()
    async def start(self, *args):
        self.tasks.append(asyncio.create_task(asyncio.Event().wait()))
        self.entered.set()
        if self.gate:
            await self.gate.wait()
        if self.fail_start:
            raise RuntimeError('initialization failed')
    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        if self.fail_stop:
            raise RuntimeError('cleanup failed')

def session(raw, market):
    result = AnalysisSession(None, None, {'BTCUSDT': D('.5')})
    result.raw, result.market = raw, market
    return result

@pytest.mark.asyncio
@pytest.mark.parametrize('which', ['raw', 'market'])
async def test_partial_start_failure_releases_both_collectors(which):
    raw, market = Collector(fail_start=which=='raw'), Collector(fail_start=which=='market')
    s = session(raw, market)
    try:
        with pytest.raises(RuntimeError, match='initialization'):
            await s.start()
        assert not s.started
        assert not raw.tasks and not market.tasks
    finally:
        raw.fail_stop = market.fail_stop = False
        await raw.stop()
        await market.stop()

@pytest.mark.asyncio
async def test_stop_cancels_startup_and_allows_restart():
    raw, market = Collector(asyncio.Event()), Collector()
    s = session(raw, market)
    start = asyncio.create_task(s.start())
    await raw.entered.wait()
    try:
        await asyncio.wait_for(s.stop(), 1)
        assert start.done()
        assert not raw.tasks and not market.tasks
        raw.gate = None
        await s.start()
        assert s.started
        await s.stop()
        assert not s.started
    finally:
        start.cancel()
        await asyncio.gather(start, return_exceptions=True)
        await raw.stop()
        await market.stop()

@pytest.mark.asyncio
async def test_cleanup_failure_still_stops_other_collector():
    raw, market = Collector(), Collector(fail_stop=True)
    s = session(raw, market)
    await s.start()
    try:
        with pytest.raises(RuntimeError, match='cleanup'):
            await s.stop()
        assert not s.started
        assert not raw.tasks and not market.tasks
    finally:
        await raw.stop()

@pytest.mark.asyncio
async def test_concurrent_starts_allocate_only_one_session():
    raw, market = Collector(asyncio.Event()), Collector()
    s = session(raw, market)
    a = asyncio.create_task(s.start())
    await raw.entered.wait()
    b = asyncio.create_task(s.start())
    await asyncio.sleep(0)
    raw.gate.set()
    try:
        outcomes = await asyncio.gather(a, b, return_exceptions=True)
        assert sum(isinstance(x, RuntimeError) for x in outcomes) == 1
        assert len(raw.tasks) == len(market.tasks) == 1
    finally:
        await s.stop()
@pytest.mark.asyncio
async def test_stop_cannot_be_overtaken_by_a_duplicate_start():
    raw, market = Collector(asyncio.Event()), Collector()
    s = session(raw, market)
    a = asyncio.create_task(s.start())
    await raw.entered.wait()
    b = asyncio.create_task(s.start())
    await asyncio.sleep(0)
    stop = asyncio.create_task(s.stop())
    try:
        await asyncio.wait_for(asyncio.shield(stop), .5)
        assert not s.started and not raw.tasks and not market.tasks
        assert isinstance((await asyncio.gather(b, return_exceptions=True))[0], RuntimeError)
    finally:
        for task in (a, b, stop):
            task.cancel()
        await asyncio.gather(a, b, stop, return_exceptions=True)
        await raw.stop()
        await market.stop()

@pytest.mark.asyncio
async def test_completion_callback_restart_cannot_overtake_stop():
    raw, market = Collector(asyncio.Event()), Collector()
    s = session(raw, market)
    first = asyncio.create_task(s.start())
    await raw.entered.wait()
    restarts = []
    first.add_done_callback(lambda _: restarts.append(asyncio.create_task(s.start())))
    stopping = asyncio.create_task(s.stop())
    try:
        await asyncio.wait_for(asyncio.shield(stopping), .2)
        outcomes = await asyncio.gather(*restarts, return_exceptions=True)
        assert outcomes and isinstance(outcomes[0], RuntimeError)
        assert not raw.tasks and not market.tasks and not s.started
    finally:
        for task in (first, stopping, *restarts):
            task.cancel()
        await asyncio.gather(first, stopping, *restarts, return_exceptions=True)
        await raw.stop()
        await market.stop()

@pytest.mark.asyncio
async def test_concurrent_stop_and_cancelled_waiter_preserve_cleanup():
    class SlowCollector(Collector):
        def __init__(self):
            super().__init__()
            self.stopping = asyncio.Event()
            self.release = asyncio.Event()
            self.stops = 0
        async def stop(self):
            self.stops += 1
            self.stopping.set()
            await self.release.wait()
            await super().stop()
    raw, market = SlowCollector(), Collector()
    s = session(raw, market)
    await s.start()
    first = asyncio.create_task(s.stop())
    await raw.stopping.wait()
    second = asyncio.create_task(s.stop())
    first.cancel()
    try:
        await asyncio.gather(first, return_exceptions=True)
        with pytest.raises(RuntimeError, match='lifecycle'):
            await s.start()
        raw.release.set()
        await asyncio.wait_for(second, 1)
        assert raw.stops == 1
        assert not raw.tasks and not market.tasks
        await s.start()
        await s.stop()
    finally:
        raw.release.set()
        await s.stop()
