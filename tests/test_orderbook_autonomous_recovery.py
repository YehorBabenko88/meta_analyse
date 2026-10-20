"""Deterministic fault injection for autonomous orderbook transport recovery."""
import asyncio
import json
import pytest
from meta_analyse.orderbook_stream import OrderBookStream


def packet(kind, uid, seq, *, bad=False):
    return json.dumps({"topic": "orderbook.50.BTCUSDT", "type": kind, "ts": 1,
        "data": {"s": "BTCUSDT", "u": uid, "seq": seq,
                 "b": [["100", "NaN" if bad else "1"]], "a": [["101", "1"]]}})


class FakeSocket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.closed = False
    async def __aenter__(self):
        return self
    async def __aexit__(self, *_):
        self.closed = True
    async def send(self, *_):
        pass
    async def recv(self):
        try:
            item = next(self.messages)
        except StopIteration:
            await asyncio.sleep(3600)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.mark.asyncio
async def test_invalid_delta_forces_new_connection_and_snapshot(monkeypatch):
    sockets = [
        FakeSocket([packet("snapshot", 1, 1), packet("delta", 2, 2, bad=True),
                    packet("delta", 3, 3)]),
        FakeSocket([packet("snapshot", 10, 10)])
    ]
    created = list(sockets)
    stop = asyncio.Event()
    events, gaps = [], []
    async def on_book(symbol, book, ts):
        events.append((symbol, book.valid, book.update_id))
        if len(events) == 2:
            stop.set()
    async def on_gap(symbols, reason):
        gaps.append(reason)
    monkeypatch.setattr("meta_analyse.orderbook_stream.websockets.connect",
                        lambda *a, **kw: sockets.pop(0))
    stream = OrderBookStream(on_book, on_gap, backoff_base=0.001, backoff_max=0.01)
    await asyncio.wait_for(stream.run(["BTCUSDT"], stop), 3)
    assert events == [("BTCUSDT", True, 1), ("BTCUSDT", True, 10)]
    assert stream.connection_epoch == 2
    assert any("invalid" in g for g in gaps)
    assert all(s.closed for s in created)


@pytest.mark.asyncio
async def test_silent_connected_feed_reconnects(monkeypatch):
    sockets = [FakeSocket([]), FakeSocket([packet("snapshot", 3, 3)])]
    stop = asyncio.Event()
    observed = []
    async def on_book(symbol, book, ts):
        observed.append(book.update_id)
        stop.set()
    async def on_gap(*_):
        pass
    monkeypatch.setattr("meta_analyse.orderbook_stream.websockets.connect",
                        lambda *a, **kw: sockets.pop(0))
    stream = OrderBookStream(on_book, on_gap, silence_timeout=0.01,
                             backoff_base=0.001, backoff_max=0.01)
    await asyncio.wait_for(stream.run(["BTCUSDT"], stop), 3)
    assert observed == [3]
    assert stream.connection_epoch == 2


@pytest.mark.asyncio
async def test_shutdown_interrupts_reconnect_backoff(monkeypatch):
    stop = asyncio.Event()
    async def failed_connect():
        raise OSError("network down")
    class BrokenSocket:
        async def __aenter__(self):
            await failed_connect()
        async def __aexit__(self, *_):
            pass
    calls = 0
    async def on_gap(*_):
        nonlocal calls
        calls += 1
        if calls >= 2:
            stop.set()
    monkeypatch.setattr("meta_analyse.orderbook_stream.websockets.connect",
                        lambda *a, **kw: BrokenSocket())
    stream = OrderBookStream(lambda *_: None, on_gap)
    await asyncio.wait_for(stream.run(["BTCUSDT"], stop), 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_message", [
    packet("delta", 2, 2, bad=True),
    packet("delta", 1, 2),
    packet("delta", 2, 1),
    packet("snapshot", 3, 3, bad=True),
    "{broken json",
])
async def test_fault_requires_new_epoch_and_snapshot(monkeypatch, bad_message):
    sockets = [
        FakeSocket([packet("snapshot", 1, 1), bad_message,
                    packet("delta", 4, 4)]),
        FakeSocket([packet("snapshot", 10, 10)])
    ]
    created = list(sockets)
    stop = asyncio.Event()
    updates, gaps = [], []
    async def on_book(symbol, book, ts):
        updates.append((book.update_id, book.valid))
        if len(updates) == 2:
            stop.set()
    async def on_gap(symbols, reason):
        gaps.append(reason)
    monkeypatch.setattr("meta_analyse.orderbook_stream.websockets.connect",
                        lambda *a, **kw: sockets.pop(0))
    stream = OrderBookStream(on_book, on_gap, backoff_base=0.001, backoff_max=0.01)
    await asyncio.wait_for(stream.run(["BTCUSDT"], stop), 3)
    assert updates == [(1, True), (10, True)]
    assert stream.connection_epoch == 2
    assert all(sock.closed for sock in created)
    assert any("UNVERIFIED" in reason for reason in gaps)


@pytest.mark.asyncio
async def test_failed_handshakes_preserve_exponential_backoff(monkeypatch):
    class StopProbe:
        def __init__(self):
            self.calls = 0
        def is_set(self):
            return self.calls >= 4
        async def wait(self):
            self.calls += 1
            raise asyncio.TimeoutError
    class BrokenSocket:
        async def __aenter__(self):
            raise ConnectionError("handshake rejected")
        async def __aexit__(self, *_):
            pass
    async def on_gap(*_):
        pass
    monkeypatch.setattr("meta_analyse.orderbook_stream.websockets.connect",
                        lambda *a, **kw: BrokenSocket())
    monkeypatch.setattr("meta_analyse.orderbook_stream.random.uniform",
                        lambda a, b: 1.0)
    delays = []
    original_wait_for = asyncio.wait_for
    async def measured_wait_for(awaitable, timeout):
        if isinstance(stop, StopProbe) and timeout <= 0.4:
            delays.append(timeout)
        return await original_wait_for(awaitable, timeout)
    # Use an event that immediately raises TimeoutError to avoid real sleeps.
    stop = StopProbe()
    monkeypatch.setattr("meta_analyse.orderbook_stream.asyncio.wait_for",
                        measured_wait_for)
    stream = OrderBookStream(lambda *_: None, on_gap,
                             backoff_base=0.1, backoff_max=0.4)
    await stream.run(["BTCUSDT"], stop)
    assert delays == [0.1, 0.2, 0.4, 0.4]
