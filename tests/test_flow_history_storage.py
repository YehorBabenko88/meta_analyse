from datetime import datetime, timezone, timedelta
from decimal import Decimal
from dataclasses import FrozenInstanceError
import pytest

from meta_analyse.flow_history_storage import read_flow_history, FlowHistorySnapshot, HistoricalTrade


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


@pytest.mark.parametrize("side,price,quantity", [
    ("Unknown", Decimal("1"), Decimal("1")),
    ("hold", Decimal("1"), Decimal("1")),
    ("Buy", Decimal("NaN"), Decimal("1")),
    ("Sell", Decimal("0"), Decimal("1")),
    ("Buy", Decimal("1"), Decimal("-1")),
    ("Sell", Decimal("1"), Decimal("Infinity")),
])
def test_orderflow_bridge_rejects_invalid_historical_values(side, price, quantity):
    from meta_analyse.flow_history_storage import to_orderflow_records
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    snapshot = FlowHistorySnapshot("BTCUSDT", start, start + timedelta(seconds=1),
        (HistoricalTrade("id-1", start, price, quantity, side),))
    with pytest.raises(ValueError):
        to_orderflow_records(snapshot)


def test_concurrent_flow_history_requests_ignore_stale_completion(monkeypatch):
    import asyncio
    import meta_analyse.desktop_service as module
    from meta_analyse.desktop_service import DesktopService

    async def scenario():
        start = datetime(2026, 10, 17, tzinfo=timezone.utc)
        end = start + timedelta(minutes=1)
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        release_first = asyncio.Event()
        release_second = asyncio.Event()

        async def fake_to_thread(func, store, *, symbol, start, end, limit):
            if symbol == "BTCUSDT":
                first_started.set()
                await release_first.wait()
            else:
                second_started.set()
                await release_second.wait()
            return FlowHistorySnapshot(symbol, start, end, ())

        monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
        service = DesktopService(object(), lambda _: None)
        first = asyncio.create_task(service.load_flow_history(
            symbol="BTCUSDT", start=start, end=end))
        await first_started.wait()
        second = asyncio.create_task(service.load_flow_history(
            symbol="ETHUSDT", start=start, end=end))
        await second_started.wait()
        release_second.set()
        await second
        assert service.snapshot().flow_history.symbol == "ETHUSDT"
        release_first.set()
        await first
        assert service.snapshot().flow_history.symbol == "ETHUSDT"
        assert service.snapshot().flow_history_request_id == 2

    asyncio.run(scenario())


def test_failed_latest_history_request_does_not_restore_stale_result(monkeypatch):
    import asyncio
    import meta_analyse.desktop_service as module
    from meta_analyse.desktop_service import DesktopService

    async def scenario():
        start = datetime(2026, 10, 17, tzinfo=timezone.utc)
        end = start + timedelta(minutes=1)
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        async def fake_to_thread(func, store, *, symbol, start, end, limit):
            if symbol == "BTCUSDT":
                first_started.set()
                await release_first.wait()
                return FlowHistorySnapshot(symbol, start, end, ())
            raise ConnectionError("secret-dsn-must-not-leak")

        monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
        service = DesktopService(object(), lambda _: None)
        old = asyncio.create_task(service.load_flow_history(
            symbol="BTCUSDT", start=start, end=end))
        await first_started.wait()
        await service.load_flow_history(symbol="ETHUSDT", start=start, end=end)
        assert service.snapshot().flow_history is None
        assert service.snapshot().status.startswith("Flow History failed")
        assert "secret-dsn-must-not-leak" not in service.snapshot().status
        release_first.set()
        await old
        assert service.snapshot().flow_history is None
        assert service.snapshot().flow_history_request_id == 2

    asyncio.run(scenario())


def test_cancelled_current_history_request_reports_status(monkeypatch):
    import asyncio
    import meta_analyse.desktop_service as module
    from meta_analyse.desktop_service import DesktopService

    async def scenario():
        started = asyncio.Event()
        async def fake_to_thread(func, store, *, symbol, start, end, limit):
            started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
        service = DesktopService(object(), lambda _: None)
        start = datetime(2026, 10, 17, tzinfo=timezone.utc)
        task = asyncio.create_task(service.load_flow_history(
            symbol="BTCUSDT", start=start, end=start + timedelta(minutes=1)))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        snapshot = service.snapshot()
        assert snapshot.flow_history is None
        assert snapshot.status == "Flow History cancelled — UNVERIFIED"
        assert snapshot.flow_history_request_id == 1

    asyncio.run(scenario())


def test_cancelled_stale_history_request_preserves_newer_success(monkeypatch):
    import asyncio
    import meta_analyse.desktop_service as module
    from meta_analyse.desktop_service import DesktopService

    async def scenario():
        start = datetime(2026, 10, 17, tzinfo=timezone.utc)
        end = start + timedelta(minutes=1)
        first_started = asyncio.Event()

        async def fake_to_thread(func, store, *, symbol, start, end, limit):
            if symbol == "BTCUSDT":
                first_started.set()
                await asyncio.Event().wait()
            return FlowHistorySnapshot(symbol, start, end, ())

        monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
        service = DesktopService(object(), lambda _: None)
        old = asyncio.create_task(service.load_flow_history(
            symbol="BTCUSDT", start=start, end=end))
        await first_started.wait()
        await service.load_flow_history(symbol="ETHUSDT", start=start, end=end)
        assert service.snapshot().status == "Flow History loaded — UNVERIFIED"
        old.cancel()
        with pytest.raises(asyncio.CancelledError):
            await old
        snapshot = service.snapshot()
        assert snapshot.flow_history.symbol == "ETHUSDT"
        assert snapshot.status == "Flow History loaded — UNVERIFIED"
        assert snapshot.flow_history_request_id == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("offset_us,expected_ms", [
    (0, 0),
    (999, 0),
    (1000, 1),
    (1999, 1),
    (-1, -1),
    (-1000, -1),
    (-1001, -2),
])
def test_orderflow_bridge_epoch_millisecond_boundaries(offset_us, expected_ms):
    from meta_analyse.flow_history_storage import to_orderflow_records
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    timestamp = epoch + timedelta(microseconds=offset_us)
    snapshot = FlowHistorySnapshot("BTCUSDT", epoch - timedelta(seconds=1),
        epoch + timedelta(seconds=1),
        (HistoricalTrade("id", timestamp, Decimal("1"), Decimal("2"), "Sell"),))
    assert to_orderflow_records(snapshot)[0]["timestamp_ms"] == expected_ms


def test_orderflow_bridge_accepts_lowercase_aggressor_side():
    from meta_analyse.flow_history_storage import to_orderflow_records
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    snapshot = FlowHistorySnapshot("BTCUSDT", start, start + timedelta(seconds=1),
        (HistoricalTrade("id", start, Decimal("1"), Decimal("2"), "buy"),))
    assert to_orderflow_records(snapshot)[0]["side"] == "buy"


@pytest.mark.parametrize("price,quantity", [
    (1.5, Decimal("2")),
    (Decimal("1"), 2.5),
    ("1.0", Decimal("2")),
    (Decimal("1"), "2.0"),
])
def test_orderflow_bridge_rejects_non_decimal_trade_fields(price, quantity):
    from meta_analyse.flow_history_storage import to_orderflow_records
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    snapshot = FlowHistorySnapshot("BTCUSDT", start, start + timedelta(seconds=1),
        (HistoricalTrade("id", start, price, quantity, "Buy"),))
    with pytest.raises(TypeError, match="Decimal"):
        to_orderflow_records(snapshot)


@pytest.mark.parametrize("offset_seconds", [-1, 60])
def test_orderflow_bridge_rejects_trades_outside_half_open_range(offset_seconds):
    from meta_analyse.flow_history_storage import to_orderflow_records
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    end = start + timedelta(seconds=60)
    snapshot = FlowHistorySnapshot("BTCUSDT", start, end,
        (HistoricalTrade("id", start + timedelta(seconds=offset_seconds),
                         Decimal("1"), Decimal("2"), "Buy"),))
    with pytest.raises(ValueError, match="outside requested interval"):
        to_orderflow_records(snapshot)


def test_orderflow_bridge_requires_explicit_snapshot_symbol():
    from meta_analyse.flow_history_storage import to_orderflow_records
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    snapshot = FlowHistorySnapshot("", start, start + timedelta(seconds=1), ())
    with pytest.raises(ValueError, match="symbol"):
        to_orderflow_records(snapshot)


@pytest.mark.parametrize("status", ["VERIFIED", "COMPLETE", ""])
def test_orderflow_bridge_rejects_unsubstantiated_verification_status(status):
    from meta_analyse.flow_history_storage import to_orderflow_records
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    snapshot = FlowHistorySnapshot("BTCUSDT", start, start + timedelta(seconds=1),
        (), status=status)
    with pytest.raises(ValueError, match="verification status"):
        to_orderflow_records(snapshot)


def test_orderflow_bridge_records_are_immutable_mappings():
    from meta_analyse.flow_history_storage import to_orderflow_records
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    snapshot = FlowHistorySnapshot("BTCUSDT", start, start + timedelta(seconds=1),
        (HistoricalTrade("id", start, Decimal("1.234567890123456789"),
                         Decimal("0.000000000000000001"), "Sell"),))
    records = to_orderflow_records(snapshot)
    assert records[0]["price"] == Decimal("1.234567890123456789")
    assert records[0]["volume"] == Decimal("0.000000000000000001")
    with pytest.raises(TypeError):
        records[0]["price"] = Decimal("0")
    assert snapshot.trades[0].price == Decimal("1.234567890123456789")


def test_orderflow_bridge_rejects_mutable_trade_collection():
    from meta_analyse.flow_history_storage import to_orderflow_records
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    snapshot = FlowHistorySnapshot("BTCUSDT", start, start + timedelta(seconds=1), [])
    with pytest.raises(TypeError, match="immutable tuple"):
        to_orderflow_records(snapshot)


@pytest.mark.parametrize("truncated", [0, 1, "false", None])
def test_orderflow_bridge_requires_boolean_truncation_flag(truncated):
    from meta_analyse.flow_history_storage import to_orderflow_records
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    snapshot = FlowHistorySnapshot("BTCUSDT", start, start + timedelta(seconds=1),
                                   (), truncated=truncated)
    with pytest.raises(TypeError, match="boolean truncation"):
        to_orderflow_records(snapshot)


@pytest.mark.parametrize("wrong_scope", ["symbol", "start", "end", "status"])
def test_worker_rejects_reader_snapshot_with_wrong_scope(monkeypatch, wrong_scope):
    import asyncio
    import meta_analyse.desktop_service as module
    from meta_analyse.desktop_service import DesktopService

    async def scenario():
        start = datetime(2026, 10, 17, tzinfo=timezone.utc)
        end = start + timedelta(minutes=1)
        async def fake_to_thread(func, store, *, symbol, start, end, limit):
            return FlowHistorySnapshot(
                "ETHUSDT" if wrong_scope == "symbol" else symbol,
                start + timedelta(seconds=1) if wrong_scope == "start" else start,
                end + timedelta(seconds=1) if wrong_scope == "end" else end,
                (), status="VERIFIED" if wrong_scope == "status" else "UNVERIFIED")
        monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
        service = DesktopService(object(), lambda _: None)
        await service.load_flow_history(symbol="BTCUSDT", start=start, end=end)
        assert service.snapshot().flow_history is None
        assert service.snapshot().flow_history_request_id == 1

    asyncio.run(scenario())


def test_stale_malformed_reader_result_does_not_replace_newer_history(monkeypatch):
    import asyncio
    import meta_analyse.desktop_service as module
    from meta_analyse.desktop_service import DesktopService

    async def scenario():
        start = datetime(2026, 10, 17, tzinfo=timezone.utc)
        end = start + timedelta(minutes=1)
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        async def fake_to_thread(func, store, *, symbol, start, end, limit):
            if symbol == "BTCUSDT":
                first_started.set()
                await release_first.wait()
                return object()
            return FlowHistorySnapshot(symbol, start, end, ())

        monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
        service = DesktopService(object(), lambda _: None)
        old = asyncio.create_task(service.load_flow_history(
            symbol="BTCUSDT", start=start, end=end))
        await first_started.wait()
        await service.load_flow_history(symbol="ETHUSDT", start=start, end=end)
        release_first.set()
        await old
        snapshot = service.snapshot()
        assert snapshot.flow_history.symbol == "ETHUSDT"
        assert snapshot.status == "Flow History loaded — UNVERIFIED"
        assert snapshot.flow_history_request_id == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("malformed", ["mutable_trades", "truncated_flag"])
def test_worker_rejects_nonimmutable_reader_snapshot(monkeypatch, malformed):
    import asyncio
    import meta_analyse.desktop_service as module
    from meta_analyse.desktop_service import DesktopService

    async def scenario():
        start = datetime(2026, 10, 17, tzinfo=timezone.utc)
        end = start + timedelta(minutes=1)
        async def fake_to_thread(func, store, *, symbol, start, end, limit):
            return FlowHistorySnapshot(symbol, start, end,
                [] if malformed == "mutable_trades" else (),
                truncated=1 if malformed == "truncated_flag" else False)
        monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
        service = DesktopService(object(), lambda _: None)
        await service.load_flow_history(symbol="BTCUSDT", start=start, end=end)
        assert service.snapshot().flow_history is None
        assert service.snapshot().flow_history_request_id == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("raw,expected_microseconds", [
    ("1735689600.000000999", 0),
    ("1735689600.000001999", 1),
    ("1735689600.999999999", 999999),
    ("253402300799.999999999", 999999),
])
def test_archive_timestamp_microsecond_truncation_without_decimal_rounding(raw, expected_microseconds):
    from meta_analyse.archive_db_import import parse_trade
    trade = parse_trade({"trdMatchID": "id", "timestamp": raw,
                         "price": "1.000000000000000001", "size": "0.000000000000000001",
                         "side": "Buy"})
    assert trade[1].microsecond == expected_microseconds
    assert trade[2] == Decimal("1.000000000000000001")
    assert trade[3] == Decimal("0.000000000000000001")


@pytest.mark.parametrize("bad_row", [
    {"trdMatchID":"id","timestamp":"1","price":"1","size":"0","side":"Buy"},
    {"trdMatchID":"id","timestamp":"1","price":"1","size":"1","side":"unknown"},
])
def test_archive_strict_trade_profile_rejects_bad_rows(bad_row):
    from meta_analyse.archive_db_import import parse_trade
    with pytest.raises(ValueError):
        parse_trade(bad_row)


def test_postgres_history_populates_orderflow_without_completeness_claim(monkeypatch):
    import asyncio
    import meta_analyse.desktop_service as module
    from meta_analyse.desktop_service import DesktopService

    async def scenario():
        start = datetime(2026, 10, 17, tzinfo=timezone.utc)
        history = FlowHistorySnapshot("BTCUSDT", start, start + timedelta(minutes=1), (
            HistoricalTrade("buy", start, Decimal("100"), Decimal("2"), "Buy"),
            HistoricalTrade("sell", start + timedelta(seconds=1), Decimal("100"), Decimal("1"), "Sell"),
        ))
        async def fake_to_thread(func, store, **kwargs):
            return history
        monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
        service = DesktopService(object(), lambda _: None)
        await service.load_flow_history(symbol="BTCUSDT", start=start, end=history.end)
        snapshot = service.snapshot()
        assert snapshot.flow_history is history
        assert len(snapshot.orderflow_rows) == 1
        assert snapshot.orderflow_rows[0].delta == "1"
        assert snapshot.orderflow_rows[0].quality == "UNVERIFIED"
        assert "UNVERIFIED" in snapshot.orderflow_status
    asyncio.run(scenario())


def test_truncated_postgres_history_refuses_orderflow_aggregation(monkeypatch):
    import asyncio
    import meta_analyse.desktop_service as module
    from meta_analyse.desktop_service import DesktopService

    async def scenario():
        start = datetime(2026, 10, 17, tzinfo=timezone.utc)
        history = FlowHistorySnapshot("BTCUSDT", start, start + timedelta(minutes=1), (
            HistoricalTrade("id", start, Decimal("100"), Decimal("2"), "Buy"),
        ), truncated=True)
        async def fake_to_thread(func, store, **kwargs):
            return history
        monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
        service = DesktopService(object(), lambda _: None)
        await service.load_flow_history(symbol="BTCUSDT", start=start, end=history.end)
        snapshot = service.snapshot()
        assert snapshot.flow_history is history
        assert snapshot.orderflow_rows == ()
        assert "truncated" in snapshot.orderflow_status.lower()
        assert "UNVERIFIED" in snapshot.orderflow_status
    asyncio.run(scenario())


def test_cancelled_history_request_cannot_publish_orderflow(monkeypatch):
    import asyncio
    import meta_analyse.desktop_service as module
    from meta_analyse.desktop_service import DesktopService

    async def scenario():
        start = datetime(2026, 10, 17, tzinfo=timezone.utc)
        started = asyncio.Event()
        async def fake_to_thread(func, store, **kwargs):
            started.set()
            await asyncio.Event().wait()
        monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
        service = DesktopService(object(), lambda _: None)
        task = asyncio.create_task(service.load_flow_history(symbol="BTCUSDT", start=start, end=start + timedelta(minutes=1)))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        snapshot = service.snapshot()
        assert snapshot.flow_history is None
        assert snapshot.orderflow_rows == ()
        assert snapshot.flow_history_request_id == 1
    asyncio.run(scenario())


def test_legacy_orderflow_archive_uses_single_readonly_query():
    from meta_analyse.orderflow_archive_reader import read_orderflow_trades

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    trade_time = start + timedelta(microseconds=123456)
    start_ms = (start - epoch).days * 86400000
    price = Decimal("0.000000000000012345678901")
    quantity = Decimal("123456.00000000000000001")
    store = FakeStore([("trade-1", trade_time, price, quantity, "Buy")])
    calls = []
    original_execute = store.connection.execute

    def record_execute(sql, params=None):
        calls.append(sql)
        return original_execute(sql, params)

    store.connection.execute = record_execute
    records = read_orderflow_trades(
        store, venue="bybit", symbol="BTCUSDT",
        start_ms=start_ms, end_ms=start_ms + 60000, limit=2,
    )
    assert records == [{
        "trade_id": "trade-1",
        "timestamp_ms": start_ms + 123,
        "price": price,
        "volume": quantity,
        "side": "Buy",
    }]
    assert store.connection.read_only
    assert sum("SELECT" in sql for sql in calls) == 1
    assert calls.count("SET TRANSACTION READ ONLY") == 1
    assert store.connection.params == (
        "bybit", "BTCUSDT", start, start + timedelta(minutes=1), 3,
    )
    assert records[0]["price"] is price
    assert records[0]["volume"] is quantity


def test_legacy_orderflow_reader_preserves_bounds_and_no_completeness_claim():
    from meta_analyse.orderflow_archive_reader import read_orderflow_trades

    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    start_ms = (start - epoch).days * 86400000
    rows = [(str(i), start, Decimal("1"), Decimal("2"), "Sell") for i in range(3)]
    store = FakeStore(rows)
    records = read_orderflow_trades(
        store, venue="bybit", symbol="BTCUSDT",
        start_ms=start_ms, end_ms=start_ms + 1000, limit=2,
    )
    assert len(records) == 2
    assert [row["trade_id"] for row in records] == ["0", "1"]
    assert all("verified" not in row and "complete" not in row for row in records)
    assert store.connection.params[-1] == 3

    for bad in (True, -1, 0):
        with pytest.raises(ValueError):
            read_orderflow_trades(
                store, venue="bybit", symbol="BTCUSDT",
                start_ms=start_ms, end_ms=start_ms + 1000, limit=bad,
            )


def test_legacy_orderflow_reader_keeps_unknown_aggressor_without_promoting_quality():
    from meta_analyse.orderflow_archive_reader import read_orderflow_trades

    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    start_ms = (start - epoch).days * 86400000
    store = FakeStore([("legacy-unknown", start, Decimal("100"), Decimal("0"), "Unknown")])
    records = read_orderflow_trades(
        store, venue="bybit", symbol="BTCUSDT",
        start_ms=start_ms, end_ms=start_ms + 1000,
    )
    assert records[0]["side"] == "Unknown"
    assert records[0]["volume"] == Decimal("0")
    assert store.connection.read_only
    assert all("verified" not in row for row in records)


def test_legacy_orderflow_reader_rejects_missing_identity_and_invalid_intervals():
    from meta_analyse.orderflow_archive_reader import read_orderflow_trades

    store = FakeStore([])
    for venue, symbol in (("", "BTCUSDT"), ("bybit", ""), (None, "BTCUSDT"), (123, "BTCUSDT"), ("bybit", None), ("bybit", 123)):
        with pytest.raises(ValueError):
            read_orderflow_trades(
                store, venue=venue, symbol=symbol, start_ms=1000, end_ms=2000
            )
    for start_ms, end_ms in ((2000, 1000), (1000, 1000), (-1, 1000),
                             (True, 2000), (1000, False)):
        with pytest.raises(ValueError):
            read_orderflow_trades(
                store, venue="bybit", symbol="BTCUSDT",
                start_ms=start_ms, end_ms=end_ms,
            )
    assert store.connection.sql is None


def test_legacy_orderflow_reader_does_not_round_large_epoch_milliseconds():
    from meta_analyse.orderflow_archive_reader import read_orderflow_trades

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    timestamp = datetime(2255, 6, 1, tzinfo=timezone.utc) + timedelta(microseconds=999999)
    delta = timestamp - epoch
    timestamp_ms = (delta.days * 86400 + delta.seconds) * 1000 + 999
    store = FakeStore([("future-id", timestamp, Decimal("0.001"), Decimal("4"), "Sell")])
    records = read_orderflow_trades(
        store, venue="bybit", symbol="BTCUSDT",
        start_ms=timestamp_ms - 999, end_ms=timestamp_ms + 1, limit=1,
    )
    assert records[0]["timestamp_ms"] == timestamp_ms
    assert records[0]["price"] == Decimal("0.001")
    assert store.connection.read_only
