from decimal import Decimal

import pytest

from meta_analyse.orderflow_metrics import Trade
from meta_analyse.orderflow_aggregation import aggregate_by_price, aggregate_by_time
from meta_analyse.orderflow_view import make_rows


def sample():
    return [
        Trade(2000, Decimal("100.19"), Decimal("3"), "buy"),
        Trade(999, Decimal("100.09"), Decimal("2"), "sell"),
        Trade(1000, Decimal("100.11"), Decimal("1"), "buy"),
    ]


def test_time_order_and_cumulative():
    rows = aggregate_by_time(sample(), 1000, initial_delta=Decimal("5"))
    assert [key for key, _ in rows] == [0, 1000, 2000]
    assert [metric.cumulative_delta for _, metric in rows] == [3, 4, 7]


def test_price_buckets_and_view():
    rows = aggregate_by_price(sample(), Decimal("0.1"))
    assert [key for key, _ in rows] == [Decimal("100.0"), Decimal("100.1")]
    assert rows[1][1].delta == Decimal("4")
    view = make_rows(rows)
    assert view[0].quality == "UNVERIFIED"
    assert view[1].cumulative_delta == "2"


@pytest.mark.parametrize("interval", [0, -1, 1.5, True])
def test_bad_interval(interval):
    with pytest.raises(ValueError):
        aggregate_by_time(sample(), interval)


@pytest.mark.parametrize("tick", ["0", "-1", "NaN"])
def test_bad_tick(tick):
    with pytest.raises(ValueError):
        aggregate_by_price(sample(), tick)


@pytest.mark.parametrize("tick_size", [True, False, "invalid", "", "NaN", "Infinity", 0, -1])
def test_invalid_tick_size_is_rejected_consistently(tick_size):
    with pytest.raises(ValueError, match="tick_size"):
        aggregate_by_price([], tick_size)


def test_aggregation_preserves_unknown_volume_and_zero_classified_imbalance():
    trades = [
        Trade(100, Decimal("100.01"), Decimal("2"), "unknown"),
        Trade(101, Decimal("100.02"), Decimal("0"), "buy"),
    ]
    time_rows = aggregate_by_time(trades, 1000)
    price_rows = aggregate_by_price(trades, Decimal("0.1"))
    for rows in (time_rows, price_rows):
        assert len(rows) == 1
        metrics = rows[0][1]
        assert metrics.buy_volume == Decimal("0")
        assert metrics.sell_volume == Decimal("0")
        assert metrics.unknown_volume == Decimal("2")
        assert metrics.imbalance is None
        assert metrics.trade_count == 2


def test_aggregation_generator_matches_materialized_input():
    trades = sample() * 10
    for aggregate, arg in ((aggregate_by_time, 1000), (aggregate_by_price, Decimal("0.1"))):
        assert aggregate(iter(trades), arg, initial_delta=Decimal("1.25")) == aggregate(
            trades, arg, initial_delta=Decimal("1.25")
        )
