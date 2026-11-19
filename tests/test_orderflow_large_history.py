"""Large-history regression without fragile machine-specific time limits."""
from decimal import Decimal

from meta_analyse.orderflow_aggregation import aggregate_by_time
from meta_analyse.orderflow_metrics import Trade


def test_100k_trades_aggregate_without_loss():
    trades = (
        Trade(i * 100, Decimal("100"), Decimal("1"),
              "buy" if i % 2 == 0 else "sell")
        for i in range(100_000)
    )
    rows = aggregate_by_time(trades, 60_000)
    assert sum(row.trade_count for _, row in rows) == 100_000
    assert sum(row.buy_volume for _, row in rows) == Decimal(50_000)
    assert sum(row.sell_volume for _, row in rows) == Decimal(50_000)
    assert rows[-1][1].cumulative_delta == 0


def test_threshold_19999_20000_20001_and_generator_single_pass():
    """Math's 20k per-call limit must not become a Meta history limit."""
    from meta_analyse.orderflow_aggregation import aggregate_by_price

    class SinglePass:
        def __init__(self, count):
            self.count = count
            self.consumed = False

        def __iter__(self):
            if self.consumed:
                raise AssertionError("generator traversed more than once")
            self.consumed = True
            for i in range(self.count):
                yield Trade(i * 100, Decimal("100.19"), Decimal("0.01"),
                            ("buy", "sell", "unknown")[i % 3])

    for count in (19_999, 20_000, 20_001):
        time_source = SinglePass(count)
        price_source = SinglePass(count)
        time_rows = aggregate_by_time(time_source, 60_000, initial_delta=Decimal("2.25"))
        price_rows = aggregate_by_price(price_source, Decimal("0.1"),
                                        initial_delta=Decimal("2.25"))
        assert sum(row.trade_count for _, row in time_rows) == count
        assert sum(row.trade_count for _, row in price_rows) == count
        expected_buy = Decimal((count + 2) // 3) / Decimal(100)
        expected_sell = Decimal((count + 1) // 3) / Decimal(100)
        expected_unknown = Decimal(count // 3) / Decimal(100)
        for result in (time_rows, price_rows):
            assert sum((row.buy_volume for _, row in result), Decimal(0)) == expected_buy
            assert sum((row.sell_volume for _, row in result), Decimal(0)) == expected_sell
            assert sum((row.unknown_volume for _, row in result), Decimal(0)) == expected_unknown
            assert result[-1][1].cumulative_delta == Decimal("2.25") + expected_buy - expected_sell
        assert time_source.consumed and price_source.consumed


def test_cross_chunk_unsorted_time_gaps_and_precise_initial_delta():
    """Late events must end up in the correct chronological bucket."""
    import itertools

    def stream():
        for i in range(20_001):
            yield Trade(3_600_000 + i, Decimal("100.125"), Decimal("0.000000000000000001"),
                        "buy")
        # The late sell event belongs to the FIRST bucket, not the last batch.
        yield Trade(0, Decimal("100.125"), Decimal("0.000000000000000003"), "sell")
        yield Trade(7_200_000, Decimal("100.125"), Decimal("5"), "unknown")

    rows = aggregate_by_time(stream(), 60_000, initial_delta=Decimal("1.000000000000000001"))
    assert [bucket for bucket, _ in rows] == [0, 3_600_000, 7_200_000]
    assert [row.trade_count for _, row in rows] == [1, 20_001, 1]
    assert rows[0][1].delta == Decimal("-0.000000000000000003")
    assert rows[1][1].buy_volume == Decimal("0.000000000000020001")
    assert rows[1][1].cumulative_delta == Decimal("1.000000000000019999")
    assert rows[2][1].unknown_volume == Decimal("5")
    assert rows[2][1].cumulative_delta == rows[1][1].cumulative_delta


def test_100k_generator_unknown_side_and_price_bucket_count():
    """A 100k generator must not overflow Math batch cap or drop unknown volume."""
    from meta_analyse.orderflow_aggregation import aggregate_by_price

    def stream():
        for i in range(100_000):
            yield Trade(i, Decimal("100.19") if i % 2 else Decimal("100.09"),
                        Decimal("0.0001"), ("buy", "sell", "unknown", "buy")[i % 4])

    rows = aggregate_by_price(stream(), Decimal("0.1"),
                              initial_delta=Decimal("0.25"))
    assert [key for key, _ in rows] == [Decimal("100.0"), Decimal("100.1")]
    assert sum(row.trade_count for _, row in rows) == 100_000
    assert sum((row.buy_volume for _, row in rows), Decimal(0)) == Decimal("5")
    assert sum((row.sell_volume for _, row in rows), Decimal(0)) == Decimal("2.5")
    assert sum((row.unknown_volume for _, row in rows), Decimal(0)) == Decimal("2.5")
    assert rows[-1][1].cumulative_delta == Decimal("2.75")


def test_math_batch_limit_remains_strict_and_stream_bucket_budget_is_bounded():
    """Streaming is a separate bounded Math contract, not a batch-limit bypass."""
    import pytest
    from market_compute_api import STREAM_ABI
    from market_profile_math import aggregate_orderflow, MAX_ORDERFLOW_BATCH
    from meta_analyse.orderflow_aggregation import aggregate_by_time

    assert STREAM_ABI == "math.market.orderflow.stream.v1"
    assert MAX_ORDERFLOW_BATCH == 20_000
    rows = [(0, Decimal("100"), Decimal("1"), "buy")] * 20_001
    with pytest.raises(ValueError, match="INVALID_AGGREGATE_BATCH"):
        aggregate_orderflow(rows, mode="time", interval_ms=1000)
    streamed = aggregate_by_time((Trade(*row) for row in rows), 1000)
    assert len(streamed) == 1
    assert streamed[0][1].trade_count == 20_001

    # More than 20k independent result buckets cannot fit the bounded Math state.
    # This is explicitly rejected; no silent truncation or disk/DB fallback.
    source = (Trade(i * 1000, Decimal("100"), Decimal("1"), "buy")
              for i in range(20_001))
    with pytest.raises(ValueError, match="STREAM_BUCKET_LIMIT"):
        aggregate_by_time(source, 1000)
