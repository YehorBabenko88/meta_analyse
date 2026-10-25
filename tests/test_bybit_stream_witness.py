"""Real stream loss witnesses, with fake sockets and no external services."""
import asyncio
import pytest
from meta_analyse.orderbook_stream import OrderBookStream
from test_orderbook_autonomous_recovery import FakeSocket, packet


@pytest.mark.asyncio
async def test_published_frame_identifies_snapshot_and_delta(monkeypatch):
    socket = FakeSocket([packet("snapshot", 1, 1), packet("delta", 2, 2)])
    monkeypatch.setattr("meta_analyse.orderbook_stream.websockets.connect", lambda *a, **kw: socket)
    stop = asyncio.Event()
    frames = []
    async def on_book(symbol, book, ts):
        frames.append(book)
        if len(frames) == 2:
            stop.set()
    async def on_gap(*args):
        pass
    await asyncio.wait_for(OrderBookStream(on_book, on_gap).run(["BTCUSDT"], stop), 1)
    assert [getattr(frame, "message_type", None) for frame in frames] == ["snapshot", "delta"]

@pytest.mark.asyncio
async def test_real_callback_queue_overflow_invalidates_epoch_and_requires_snapshot(monkeypatch):
    from meta_analyse.market_health import MarketHealthMonitor
    sockets = [FakeSocket([packet("snapshot", 1, 1), packet("delta", 2, 2),
                           packet("delta", 3, 3)]),
               FakeSocket([packet("delta", 4, 4)]),
               FakeSocket([packet("snapshot", 10, 10)])]
    created = list(sockets)
    monkeypatch.setattr("meta_analyse.orderbook_stream.websockets.connect", lambda *a, **kw: sockets.pop(0))
    stop = asyncio.Event()
    queue = asyncio.Queue(maxsize=1)
    health = MarketHealthMonitor()
    published, invalidations = [], []
    async def on_book(symbol, book, ts):
        # This QueueFull is thrown by the actual stream callback, not a toy
        # helper that independently resets an OrderBook.
        queue.put_nowait(book)
        health.book(symbol)
        published.append(book.update_id)
        if book.update_id == 10:
            stop.set()
    async def on_gap(symbols, reason):
        health.gap("orderbook", symbols)
        invalidations.append((stream.connection_epoch,
                              all(not b.valid for b in stream.books.values()),
                              health.snapshot(symbols)[0].orderbook))
        while not queue.empty():
            queue.get_nowait()
            queue.task_done()
    stream = OrderBookStream(on_book, on_gap, backoff_base=0.001, backoff_max=0.01)
    await asyncio.wait_for(stream.run(["BTCUSDT"], stop), 2)
    assert published == [1, 10]
    assert stream.connection_epoch == 3
    assert all(invalid and status == "UNVERIFIED" for _, invalid, status in invalidations)
    assert all(socket.closed for socket in created)
    assert queue.qsize() == 1


def test_real_ui_health_monotonic_staleness_and_gap_recovery(monkeypatch):
    from meta_analyse.market_health import MarketHealthMonitor
    now = [10.0]
    monkeypatch.setattr("meta_analyse.feed_watchdog.monotonic", lambda: now[0])
    health = MarketHealthMonitor(stale_after_seconds=8)
    assert health.snapshot(["BTCUSDT"])[0].combined == "UNVERIFIED"
    health.execution("BTCUSDT")
    health.book("BTCUSDT")
    assert health.snapshot(["BTCUSDT"])[0].combined == "PROVISIONAL"
    now[0] = 19
    assert health.snapshot(["BTCUSDT"])[0].combined == "STALE"
    health.gap("orderbook", ["BTCUSDT"])
    assert health.snapshot(["BTCUSDT"])[0].combined == "UNVERIFIED"
    health.book("BTCUSDT")
    assert health.snapshot(["BTCUSDT"])[0].orderbook == "PROVISIONAL"


def test_numeric_sequence_jump_does_not_invent_exchange_packet_loss():
    from meta_analyse.orderbook import OrderBook
    import json
    book = OrderBook("BTCUSDT")
    assert book.apply(json.loads(packet("snapshot", 1, 10)))
    assert book.apply(json.loads(packet("delta", 7, 100)))
    assert book.valid
    assert not book.apply(json.loads(packet("delta", 8, 99)))
    assert not book.valid
    assert not book.apply(json.loads(packet("delta", 9, 101)))
    assert book.apply(json.loads(packet("snapshot", 10, 102)))
