from decimal import Decimal

import pytest

from meta_analyse.orderflow_metrics import Trade, calculate


def trade(side, volume, price="100"):
    return Trade(1, Decimal(price), Decimal(volume), side)


def test_buy_sell_delta_and_imbalance():
    result = calculate([trade("buy", "3"), trade("sell", "1")])
    assert result.buy_volume == Decimal("3")
    assert result.sell_volume == Decimal("1")
    assert result.delta == Decimal("2")
    assert result.imbalance == Decimal("0.5")
    assert result.cumulative_delta == Decimal("2")


def test_unknown_volume_is_not_misclassified():
    result = calculate([trade("unknown", "7")])
    assert result.unknown_volume == Decimal("7")
    assert result.imbalance is None
    assert result.delta == 0


def test_cumulative_seed():
    assert calculate([trade("sell", "2")], initial_delta=Decimal("10")).cumulative_delta == 8


@pytest.mark.parametrize("side,volume,price", [
    ("bad", "1", "100"),
    ("buy", "-1", "100"),
    ("buy", "NaN", "100"),
    ("buy", "1", "Infinity"),
    ("buy", "1", "0"),
])
def test_invalid_trade_rejected(side, volume, price):
    with pytest.raises(ValueError):
        calculate([trade(side, volume, price)])


@pytest.mark.parametrize("seed", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), 0, "0"])
def test_nonfinite_or_non_decimal_cumulative_seed_rejected(seed):
    with pytest.raises(ValueError, match="initial_delta"):
        calculate([], initial_delta=seed)
