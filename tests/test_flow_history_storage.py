from datetime import datetime, timezone, timedelta
from decimal import Decimal
from dataclasses import FrozenInstanceError
import pytest

from meta_analyse.flow_history_storage import read_flow_history, FlowHistorySnapshot, HistoricalTrade, HistoricalTrade


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


def test_rejects_naive_datetime_and_invalid_limits():
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    for bad_start in (start.replace(tzinfo=None),):
        with pytest.raises(ValueError, match="timezone-aware"):
            read_flow_history(FakeStore([]), symbol="BTCUSDT",
                              start=bad_start, end=start + timedelta(seconds=1))
    for bad_limit in (0, -1, True, 100001):
        with pytest.raises(ValueError, match="limit"):
            read_flow_history(FakeStore([]), symbol="BTCUSDT",
                              start=start, end=start + timedelta(seconds=1),
                              limit=bad_limit)


def test_half_open_time_window_is_parameterized_and_utc_normalized():
    from datetime import timezone as tz
    start = datetime(2026, 10, 17, 3, tzinfo=tz(timedelta(hours=3)))
    end = start + timedelta(minutes=1)
    store = FakeStore([])
    result = read_flow_history(store, symbol="ETHUSDT", start=start, end=end)
    assert result.start == datetime(2026, 10, 17, tzinfo=timezone.utc)
    assert result.end == result.start + timedelta(minutes=1)
    assert "trade_ts >= %s AND trade_ts < %s" in store.connection.sql
    assert store.connection.params[1:4] == ("ETHUSDT", result.start, result.end)


def test_worker_snapshot_exposes_history_before_runtime_initialization():
    from meta_analyse.desktop_service import DesktopService
    service = DesktopService(None, lambda _: None)
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    history = FlowHistorySnapshot("BTCUSDT", start, start + timedelta(seconds=1), ())
    service.flow_history = history
    result = service.snapshot()
    assert result.flow_history is history
    assert result.flow_history.status == "UNVERIFIED"
    assert result.flow_history_request_id == 0
    service._history_generation = 2
    assert service.snapshot().flow_history_request_id == 2


def test_orderflow_bridge_preserves_decimals_and_exact_milliseconds():
    from meta_analyse.flow_history_storage import to_orderflow_records
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    timestamp = start + timedelta(microseconds=123456)
    price = Decimal("0.000000000000000123456789")
    quantity = Decimal("123456789.000000000000001")
    snapshot = FlowHistorySnapshot("BTCUSDT", start, start + timedelta(seconds=1),
        (HistoricalTrade("id-1", timestamp, price, quantity, "Buy"),))
    records = to_orderflow_records(snapshot)
    expected_ms = int((start - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()) * 1000 + 123
    assert records == ({"timestamp_ms": expected_ms, "price": price,
                        "volume": quantity, "side": "buy"},)
    assert snapshot.status == "UNVERIFIED"
    assert snapshot.trades[0].quantity is quantity
