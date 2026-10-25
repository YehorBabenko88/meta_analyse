"""Offline backpressure and loss-contract tests; no network or DB."""
import asyncio
import pytest
from meta_analyse.orderbook import OrderBook
from meta_analyse.orderbook_stream import BookSnapshot


def msg(kind, uid, seq):
    return {"type": kind, "data": {"s": "BTCUSDT", "u": uid, "seq": seq,
            "b": [["100", "1"]], "a": [["101", "1"]]}}


@pytest.mark.asyncio
async def test_slow_consumer_queue_overflow_fails_closed():
    queue = asyncio.Queue(maxsize=2)
    book = OrderBook("BTCUSDT")
    assert book.apply(msg("snapshot", 1, 1))
    async def enqueue(snapshot):
        try:
            queue.put_nowait(snapshot)
        except asyncio.QueueFull:
            book.reset()
            return False
        return True
    assert await enqueue(BookSnapshot.from_book(book))
    assert await enqueue(BookSnapshot.from_book(book))
    assert not await enqueue(BookSnapshot.from_book(book))
    assert not book.valid
    assert not book.apply(msg("delta", 2, 2))
    assert book.apply(msg("snapshot", 3, 3))


@pytest.mark.asyncio
async def test_out_of_order_after_snapshot_never_promotes_valid():
    book = OrderBook("BTCUSDT")
    assert book.apply(msg("snapshot", 10, 10))
    assert not book.apply(msg("delta", 9, 11))
    assert not book.valid
    assert not book.apply(msg("delta", 12, 12))
    assert book.apply(msg("snapshot", 13, 13))
