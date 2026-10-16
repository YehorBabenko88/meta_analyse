from decimal import Decimal

from meta_analyse.orderflow_adapters import StreamingTrades, from_records


def test_historical_records_are_normalized():
    rows = [{"timestamp_ms": 1000, "price": "10.5", "volume": "2.25", "side": "BUY"}]
    result = tuple(from_records(rows))
    assert result[0].price == Decimal("10.5")
    assert result[0].volume == Decimal("2.25")
    assert result[0].side == "buy"


def test_bounded_stream_tracks_evictions():
    stream = StreamingTrades(capacity=2)
    stream.append("first")
    stream.append("second")
    stream.append("third")
    assert stream.snapshot() == ("second", "third")
    assert stream.dropped == 1
