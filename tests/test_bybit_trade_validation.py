"""Offline raw transport validation before any durable execution callback."""
import pytest
from decimal import Decimal
from meta_analyse.raw_trades import parse_public_trade


def message(**changes):
    row = {"s": "BTCUSDT", "i": "trade-1", "T": 1767225600123,
           "p": "90000.01", "v": "0.00012", "S": "Buy"}
    row.update(changes)
    return {"topic": "publicTrade.BTCUSDT", "data": [row]}


@pytest.mark.parametrize("changes", [
    {"p": "Infinity"}, {"v": "Infinity"}, {"p": "NaN"}, {"v": "-Infinity"},
    {"T": True}, {"T": 1.5}, {"T": "1767225600123"}, {"T": 0}, {"T": -1},
    {"i": None}, {"i": 123}, {"i": ""}, {"s": None}, {"s": "ETHUSDT"},
    {"p": 100}, {"v": True},
])
def test_malformed_execution_cannot_reach_pipeline(changes):
    with pytest.raises(ValueError, match="Malformed publicTrade"):
        parse_public_trade(message(**changes))


@pytest.mark.parametrize("side", ["Buy", "Sell"])
def test_valid_execution_preserves_exact_exchange_values(side):
    event, = parse_public_trade(message(S=side))
    assert event.symbol == "BTCUSDT"
    assert event.execution_id == "trade-1"
    assert event.timestamp_ms == 1767225600123
    assert event.price == Decimal("90000.01")
    assert event.quantity == Decimal("0.00012")
    assert event.taker_side == side
