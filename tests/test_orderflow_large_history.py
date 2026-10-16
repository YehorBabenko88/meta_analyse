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
