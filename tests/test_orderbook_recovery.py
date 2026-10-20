"""Fail-closed Bybit orderbook state transitions."""
from decimal import Decimal
import pytest
from meta_analyse.orderbook import OrderBook


def message(kind, uid, seq, bids=None, asks=None):
    return {"type": kind, "data": {"s": "BTCUSDT", "u": uid, "seq": seq,
            "b": [["100", "1"]] if bids is None else bids,
            "a": [["101", "1"]] if asks is None else asks}}


def test_delta_cannot_bootstrap_book_even_with_restart_uid():
    book = OrderBook("BTCUSDT")
    assert not book.apply(message("delta", 1, 1))
    assert not book.valid
    assert book.apply(message("snapshot", 1, 2))


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_levels_fail_closed(bad):
    book = OrderBook("BTCUSDT")
    with pytest.raises(ValueError):
        book.apply(message("snapshot", 1, 1, bids=[["100", bad]]))
    assert not book.valid


@pytest.mark.parametrize("uid,seq", [(True, 1), ("2", 2), (-1, 2), (2, None)])
def test_invalid_update_ids_rejected(uid, seq):
    book = OrderBook("BTCUSDT")
    assert not book.apply(message("snapshot", uid, seq))
    assert not book.valid


def test_duplicate_and_out_of_order_require_new_snapshot():
    book = OrderBook("BTCUSDT")
    assert book.apply(message("snapshot", 1, 1))
    assert book.apply(message("delta", 2, 2))
    assert not book.apply(message("delta", 2, 3))
    assert not book.apply(message("delta", 3, 4))
    assert book.apply(message("snapshot", 5, 5))
    assert book.valid
