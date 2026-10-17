from decimal import Decimal
import pytest

from meta_analyse.orderflow_adapters import StreamingTrades, from_records
from meta_analyse.orderflow_metrics import Trade


def trade(n):
    return Trade(n, Decimal("10"), Decimal("1"), "buy")


def test_historical_records_are_normalized():
    rows = [{"timestamp_ms": 1000, "price": "10.5", "volume": "2.25", "side": "BUY"}]
    result = tuple(from_records(rows))
    assert result[0].price == Decimal("10.5")
    assert result[0].volume == Decimal("2.25")
    assert result[0].side == "buy"


@pytest.mark.parametrize("record", [
    {"timestamp_ms": True, "price": "10", "volume": "1"},
    {"timestamp_ms": 1.5, "price": "10", "volume": "1"},
    {"timestamp_ms": 1, "price": "NaN", "volume": "1"},
    {"timestamp_ms": 1, "price": "10", "volume": "-1"},
])
def test_invalid_record(record):
    with pytest.raises(ValueError):
        tuple(from_records([record]))


def test_bounded_stream_tracks_evictions_and_gaps():
    stream = StreamingTrades(capacity=2)
    stream.append(trade(1))
    stream.append(trade(2))
    assert stream.continuous
    stream.append(trade(3))
    assert stream.snapshot() == (trade(2), trade(3))
    assert stream.dropped == 1
    assert not stream.continuous
    stream.reset()
    assert stream.continuous
    stream.mark_gap()
    assert not stream.continuous


def test_stream_rejects_unnormalized_input():
    stream = StreamingTrades()
    with pytest.raises(TypeError):
        stream.append("not a trade")


@pytest.mark.parametrize("field", ["price", "volume"])
@pytest.mark.parametrize("bad", ["broken", "", "1.2.3"])
def test_malformed_decimal_records_raise_value_error(field, bad):
    record = {"timestamp_ms": 1, "price": "100", "volume": "1", "side": "buy"}
    record[field] = bad
    with pytest.raises(ValueError, match="valid decimals"):
        list(from_records([record]))


@pytest.mark.parametrize("invalid", [
    Trade(True, Decimal("10"), Decimal("1"), "buy"),
    Trade(1, Decimal("NaN"), Decimal("1"), "buy"),
    Trade(1, Decimal("10"), Decimal("-1"), "buy"),
    Trade(1, Decimal("10"), Decimal("1"), "invalid"),
])
def test_invalid_stream_trade_does_not_evict_valid_history(invalid):
    stream = StreamingTrades(capacity=1)
    stream.append(trade(1))
    with pytest.raises(ValueError):
        stream.append(invalid)
    assert stream.snapshot() == (trade(1),)
    assert stream.dropped == 0
    assert stream.continuous


def test_out_of_order_stream_invalidates_continuity_without_dropping():
    stream = StreamingTrades(capacity=3)
    stream.append(trade(10))
    stream.append(trade(10))  # same millisecond is permitted
    assert stream.continuous
    stream.append(trade(9))
    assert stream.snapshot() == (trade(10), trade(10), trade(9))
    assert stream.dropped == 0
    assert stream.gaps == 1
    assert not stream.continuous
