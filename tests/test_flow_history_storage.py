from datetime import datetime, timezone, timedelta
from decimal import Decimal
from dataclasses import FrozenInstanceError
import pytest

from meta_analyse.flow_history_storage import read_flow_history, FlowHistorySnapshot


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None
        self.read_only = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def transaction(self):
        return self

    def execute(self, sql, params=None):
        if sql == "SET TRANSACTION READ ONLY":
            self.read_only = True
        else:
            self.sql, self.params = sql, params
        return self

    def fetchall(self):
        return self.rows


class FakeStore:
    def __init__(self, rows):
        self.connection = FakeConnection(rows)

    def connect(self):
        return self.connection


def test_decimal_precision_and_immutable_snapshot():
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    end = start + timedelta(minutes=1)
    price = Decimal("0.000000000000000000123456789123456789")
    quantity = Decimal("123456789.0000000000000000000001")
    store = FakeStore([("id-1", start, price, quantity, "Buy")])
    snapshot = read_flow_history(store, symbol="BTCUSDT", start=start, end=end)
    assert snapshot.status == "UNVERIFIED"
    assert snapshot.trades[0].price == price
    assert snapshot.trades[0].quantity == quantity
    assert isinstance(snapshot.trades, tuple)
    assert store.connection.read_only
    assert store.connection.params == ("bybit", "BTCUSDT", start, end, 5001)
    with pytest.raises(FrozenInstanceError):
        snapshot.status = "VERIFIED"


@pytest.mark.parametrize("symbol,start_offset,end_offset", [
    ("", 0, 60), ("BTCUSDT", 60, 0), ("BTCUSDT", 0, 0)])
def test_requires_explicit_instrument_and_range(symbol, start_offset, end_offset):
    now = datetime(2026, 10, 17, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        read_flow_history(FakeStore([]), symbol=symbol,
                          start=now + timedelta(seconds=start_offset),
                          end=now + timedelta(seconds=end_offset))


def test_truncation_never_claims_completeness():
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    rows = [(str(i), start, Decimal("1"), Decimal("2"), "Sell") for i in range(3)]
    snapshot = read_flow_history(FakeStore(rows), symbol="ETHUSDT",
                                 start=start, end=start + timedelta(seconds=1), limit=2)
    assert snapshot.truncated is True
    assert snapshot.status == "UNVERIFIED"
    assert len(snapshot.trades) == 2
