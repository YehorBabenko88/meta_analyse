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
