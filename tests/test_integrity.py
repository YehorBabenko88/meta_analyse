from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
import pytest
from meta_analyse.core import Candle
from meta_analyse.history import validate_fixed_interval, yearly_from_daily
from meta_analyse.raw_trades import parse_public_trade

T = datetime(2026, 1, 1, tzinfo=timezone.utc)

def test_raw_execution_exact_values():
    trades = parse_public_trade({"topic":"publicTrade.BTCUSDT","data":[
        {"s":"BTCUSDT","i":"trade-1","T":1767225600123,"p":"90000.01","v":"0.00012","S":"Buy"}]})
    assert len(trades) == 1
    assert trades[0].execution_id == "trade-1"
    assert trades[0].price * trades[0].quantity == D("10.8000012")

def test_invalid_trade_fails_closed():
    with pytest.raises(ValueError):
        parse_public_trade({"topic":"publicTrade.BTCUSDT","data":[
            {"s":"BTCUSDT","i":"x","T":1,"p":"0","v":"1","S":"Buy"}]})

def test_coverage_reports_missing_bar():
    candles = [Candle(T,D(2),D(1),D(1),D(2))]
    c = validate_fixed_interval(candles,T,T+timedelta(hours=2),timedelta(hours=1))
    assert not c.complete and c.expected == 2 and c.received == 1
    assert c.missing_starts == (T+timedelta(hours=1),)

def test_yearly_rejects_incomplete_history():
    assert yearly_from_daily([Candle(T,D(2),D(1),D(1),D(2))],
                             datetime(2027,1,1,tzinfo=timezone.utc)) == []
