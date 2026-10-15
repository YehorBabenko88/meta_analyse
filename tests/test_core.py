from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from meta_analyse.core import Candle, Trade, new_minute, untouched_levels, PaperEngine, RollingFlow, price_bucket
from meta_analyse.runtime import Runtime

T = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)

def trade(second, price, size="1", side="Buy"):
    return Trade("BTCUSDT", T + timedelta(seconds=second), D(price), D(size), side)

def test_bucket():
    assert price_bucket(D("1.234"), D("0.01")) == D("1.23")

def test_poc_tie_nearest_close():
    m = new_minute(trade(0, "100"), D("1"))
    m.add(trade(1, "101"))
    assert m.poc == D("101")

def test_levels_wick_touch_invalidates():
    candles = [Candle(T, D("101"), D("99"), D("100"), D("100")),
               Candle(T + timedelta(days=1), D("102"), D("99"), D("100"), D("101"))]
    levels = untouched_levels(candles, "D1")
    assert {(l.kind, l.price) for l in levels} == {("high", D("102")), ("low", D("99"))}

def test_paper_short_target_fees():
    e = PaperEngine()
    e.enabled = True
    e.on_closed_minute("BTCUSDT", new_minute(trade(0, "100"), D("1")))
    e.on_trade(trade(61, "102"))
    assert e.positions["BTCUSDT"].side == "short"
    result = e.on_trade(trade(62, "100"))
    assert result.reason == "target"
    assert result.fees > 0 and result.net < result.gross
    assert "BTCUSDT" not in e.positions

def test_no_touch_beyond_next_minute():
    e = PaperEngine()
    e.enabled = True
    e.on_closed_minute("BTCUSDT", new_minute(trade(0, "100"), D("1")))
    e.on_trade(trade(121, "103"))
    assert not e.positions

def test_one_open_position_per_symbol():
    e = PaperEngine()
    e.enabled = True
    e.on_closed_minute("BTCUSDT", new_minute(trade(0, "100"), D("1")))
    e.on_trade(trade(60, "98"))
    e.on_trade(trade(61, "97.9"))
    assert len(e.positions) == 1

def test_flow_wall_ratio():
    flow = RollingFlow()
    flow.add(trade(1, "10", "100"))
    score = flow.wall_score(D("10"), D("100"), T + timedelta(seconds=2))
    assert score["ratios"][60] == D("1")

def test_runtime_gap_disables_poc_reference():
    class Dummy: pass
    r = Runtime(Dummy(), Dummy())
    r.symbols = ["BTCUSDT"]
    def message(s, price):
        t = T + timedelta(seconds=s)
        return {"Type":"trade_update", "Data":{"ticker":"BTCUSDT", "trades":[{
            "price":price, "size":"1", "side":"Buy", "time":t.isoformat()}]}}
    r.receive(message(0, "100"))
    r.receive(message(130, "103"))
    assert "BTCUSDT" not in r.paper.reference
