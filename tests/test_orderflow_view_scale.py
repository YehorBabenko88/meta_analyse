"""Deterministic UI data-model scaling checks (no exchange or display needed)."""
from decimal import Decimal

from meta_analyse.orderflow_metrics import FlowMetrics
from meta_analyse.orderflow_view import make_rows


def test_ten_thousand_history_rows_are_immutable_and_complete():
    metrics = FlowMetrics(
        Decimal("2"), Decimal("1"), Decimal("0"),
        Decimal("1"), Decimal("1"), Decimal("0.333"), 2
    )
    buckets = ((i * 60_000, metrics) for i in range(10_000))
    rows = make_rows(buckets)
    assert len(rows) == 10_000
    assert rows[0].bucket == "0"
    assert rows[-1].bucket == str(9_999 * 60_000)
    assert rows[0].quality == rows[-1].quality == "UNVERIFIED"
    assert rows[0].delta == "1"
