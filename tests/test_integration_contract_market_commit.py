"""Offline, bounded integration-contract witness; no external connections.

This is NOT a full Bybit→PostgreSQL→Qt E2E proof. It checks that a
production-style market callback cannot promote a failed write to telemetry.
"""
import asyncio
from decimal import Decimal
from types import SimpleNamespace
import pytest
from meta_analyse.market_collector import MarketCollector


@pytest.mark.asyncio
async def test_failed_orderbook_commit_never_promotes_telemetry():
    class FailingDB:
        def book(self, *_):
            raise OSError("synthetic database failure")
    class Telemetry:
        def __init__(self):
            self.observed = []
        def observe(self, *args):
            self.observed.append(args)
    telemetry = Telemetry()
    collector = MarketCollector(None, None, telemetry=telemetry)
    collector.db = FailingDB()
    published = []
    async def on_book(*args):
        published.append(args)
    collector.on_book = on_book
    snapshot = SimpleNamespace(valid=True, symbol="BTCUSDT",
        bids={Decimal("100"): Decimal("1")},
        asks={Decimal("101"): Decimal("1")}, update_id=1, sequence=1)
    with pytest.raises(OSError, match="synthetic database failure"):
        await collector._book("BTCUSDT", snapshot, 1)
    assert telemetry.observed == []
    assert published == []


@pytest.mark.asyncio
async def test_successful_commit_precedes_telemetry_and_publish():
    order = []
    class SuccessfulDB:
        def book(self, *_):
            order.append("commit")
    class Telemetry:
        def observe(self, *_):
            order.append("telemetry")
    async def published(*_):
        order.append("publish")
    collector = MarketCollector(None, None, telemetry=Telemetry(), on_book=published)
    collector.db = SuccessfulDB()
    await collector._book("BTCUSDT", SimpleNamespace(valid=True), 1)
    assert order == ["commit", "telemetry", "publish"]


@pytest.mark.asyncio
async def test_blocked_write_cannot_publish_before_release():
    import threading
    entered, release = threading.Event(), threading.Event()
    events = []
    class BlockingDB:
        def book(self, *_):
            entered.set()
            if not release.wait(3):
                raise TimeoutError("synthetic blocked write")
            events.append("committed")
    class Telemetry:
        def observe(self, *_):
            events.append("observed")
    async def publish(*_):
        events.append("published")
    collector = MarketCollector(None, None, telemetry=Telemetry(), on_book=publish)
    collector.db = BlockingDB()
    task = asyncio.create_task(collector._book("BTCUSDT", SimpleNamespace(valid=True), 1))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        await asyncio.sleep(0)
        assert events == []
        assert not task.done()
    finally:
        release.set()
    await asyncio.wait_for(task, 3)
    assert events == ["committed", "observed", "published"]


@pytest.mark.asyncio
async def test_cancellation_during_blocked_write_never_publishes():
    import threading
    entered, release = threading.Event(), threading.Event()
    events = []
    class BlockingDB:
        def book(self, *_):
            entered.set()
            if not release.wait(3):
                raise TimeoutError("synthetic blocked write")
            events.append("committed")
    class Telemetry:
        def observe(self, *_):
            events.append("observed")
    async def publish(*_):
        events.append("published")
    collector = MarketCollector(None, None, telemetry=Telemetry(), on_book=publish)
    collector.db = BlockingDB()
    task = asyncio.create_task(collector._book("BTCUSDT", SimpleNamespace(valid=True), 1))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done(), "active DB write must retain cancellation ownership"
        assert events == []
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 3)
    assert events == ["committed"]


@pytest.mark.asyncio
async def test_database_write_exception_does_not_increment_gapless_health():
    class FailingDB:
        def book(self, *_):
            raise RuntimeError("transaction rolled back")
    class Telemetry:
        def __init__(self):
            self.events = 0
            self.gaps = 0
        def observe(self, *_):
            self.events += 1
        def gap(self, *_):
            self.gaps += 1
    telemetry = Telemetry()
    collector = MarketCollector(None, None, telemetry=telemetry)
    collector.db = FailingDB()
    with pytest.raises(RuntimeError, match="transaction rolled back"):
        await collector._book("BTCUSDT", SimpleNamespace(valid=True), 1)
    assert telemetry.events == 0
    assert telemetry.gaps == 0


@pytest.mark.asyncio
async def test_gap_invalidates_telemetry_without_persisted_success():
    order = []
    class Telemetry:
        def gap(self, source, symbol):
            order.append(("gap", source, symbol))
        def observe(self, *_):
            raise AssertionError("gap must not be counted as successful observation")
    async def on_gap(symbols, reason):
        order.append(("callback", tuple(symbols), reason))
    collector = MarketCollector(None, None, telemetry=Telemetry(), on_gap=on_gap)
    await collector._gap(["BTCUSDT"], "synthetic sequence regression")
    assert order == [
        ("gap", "orderbook", "BTCUSDT"),
        ("callback", ("BTCUSDT",), "synthetic sequence regression"),
    ]
