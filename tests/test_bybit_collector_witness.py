"""Collector persistence and drain witnesses; fake connection, no PostgreSQL server."""
import asyncio
from threading import Event
import pytest
from meta_analyse.market_collector import MarketCollector
from meta_analyse.orderbook import OrderBook
from meta_analyse.orderbook_stream import BookSnapshot


def snapshot():
    book = OrderBook("BTCUSDT")
    assert book.apply({"type": "snapshot", "data": {"s": "BTCUSDT", "u": 7,
        "seq": 12, "b": [["100", "1"]], "a": [["101", "1"]]}})
    return BookSnapshot.from_book(book, "snapshot")


class Store:
    def __init__(self, *, fail=False, block=False):
        self.fail, self.block = fail, block
        self.started, self.release, self.committed = Event(), Event(), Event()
        self.statements = []
    def connect(self):
        owner = self
        class Connection:
            def __enter__(self):
                return self
            def execute(self, sql, params):
                owner.statements.append((sql, params))
                owner.started.set()
                if owner.block:
                    assert owner.release.wait(3), "test failed to release fake store"
                if owner.fail:
                    raise RuntimeError("simulated rollback")
            def __exit__(self, typ, *_):
                if typ is None:
                    owner.committed.set()
        return Connection()


@pytest.mark.asyncio
async def test_book_sql_identity_commits_before_healthy_callback():
    store = Store()
    seen = []
    async def on_book(symbol, book, ts):
        assert store.committed.is_set()
        seen.append((symbol, book.update_id, book.sequence, ts))
    collector = MarketCollector(store, None, on_book=on_book)
    await collector._book("BTCUSDT", snapshot(), 1000)
    assert seen == [("BTCUSDT", 7, 12, 1000)]
    sql, params = store.statements[0]
    assert "orderbook_observations" in sql
    assert params[0] == "BTCUSDT" and params[2:4] == (7, 12)
    assert collector.telemetry.snapshot().events == (("orderbook:BTCUSDT", 1),)
    # This witnesses callback ordering and SQL identity, not server durability,
    # a PostgreSQL checkpoint/LSN, or Qt rendering.


@pytest.mark.asyncio
async def test_rollback_cannot_publish_or_refresh_telemetry():
    store = Store(fail=True)
    seen = []
    async def on_book(*args):
        seen.append(args)
    collector = MarketCollector(store, None, on_book=on_book)
    with pytest.raises(RuntimeError, match="simulated rollback"):
        await collector._book("BTCUSDT", snapshot(), 1000)
    assert not seen and not store.committed.is_set()
    assert collector.telemetry.snapshot().events == ()


@pytest.mark.asyncio
async def test_shutdown_drains_inflight_book_write_without_late_callback():
    store = Store(block=True)
    seen = []
    async def on_book(*args):
        seen.append(args)
    collector = MarketCollector(store, None, on_book=on_book)
    task = asyncio.create_task(collector._book("BTCUSDT", snapshot(), 1000))
    collector.tasks = [task]
    assert await asyncio.to_thread(store.started.wait, 1)
    stopping = asyncio.create_task(collector.stop())
    try:
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not stopping.done()
        assert not store.committed.is_set()
    finally:
        store.release.set()
        await asyncio.wait_for(stopping, 2)
    assert store.committed.is_set()
    assert task.cancelled() and not collector.tasks and not seen
    assert collector.telemetry.snapshot().events == ()


@pytest.mark.asyncio
async def test_cancelled_rollback_drains_and_logs_original_failure(caplog):
    # Select PR50's useful failure-during-cancellation witness, using the real
    # MarketStore transaction boundary rather than replacing db.book itself.
    store = Store(block=True, fail=True)
    published = []
    async def on_book(*args):
        published.append(args)
    collector = MarketCollector(store, None, on_book=on_book)
    task = asyncio.create_task(collector._book("BTCUSDT", snapshot(), 1000))
    assert await asyncio.to_thread(store.started.wait, 1)
    try:
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "rollback worker lost ownership under repeated cancellation"
    finally:
        store.release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 2)
    assert not store.committed.is_set()
    assert not published
    assert collector.telemetry.snapshot().events == ()
    assert "simulated rollback" in caplog.text
