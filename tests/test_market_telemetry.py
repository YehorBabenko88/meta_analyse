from concurrent.futures import ThreadPoolExecutor
import pytest
from meta_analyse.market_telemetry import MarketTelemetry

def test_telemetry_counts_and_stable_snapshot():
    t=MarketTelemetry()
    t.observe("trades","BTCUSDT")
    t.observe("trades","BTCUSDT")
    t.gap("orderbook","BTCUSDT")
    assert t.snapshot().events==(("trades:BTCUSDT",2),)
    assert t.snapshot().gaps==(("orderbook:BTCUSDT",1),)

def test_telemetry_concurrent_writes():
    t=MarketTelemetry()
    def write(_):
        for _ in range(100):
            t.observe("trades","BTCUSDT")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write,range(8)))
    assert t.snapshot().events==(("trades:BTCUSDT",800),)

def test_telemetry_rejects_empty_keys():
    t=MarketTelemetry()
    with pytest.raises(ValueError):
        t.observe("","BTCUSDT")
    with pytest.raises(ValueError):
        t.gap("orderbook","")

def test_age_tracks_last_persisted_event_with_monotonic_clock(monkeypatch):
    import meta_analyse.market_telemetry as module
    clock=[100.0]
    monkeypatch.setattr(module,"monotonic",lambda:clock[0])
    t=MarketTelemetry()
    assert t.ages()==()
    t.observe("orderbook","BTCUSDT")
    clock[0]=102.5
    assert t.ages()==(("orderbook:BTCUSDT",2.5),)
    t.gap("orderbook","BTCUSDT")
    assert t.ages()==(("orderbook:BTCUSDT",2.5),)
    t.observe("orderbook","BTCUSDT")
    assert t.ages()==(("orderbook:BTCUSDT",0.0),)
    assert t.ages(now=101.0)==(("orderbook:BTCUSDT",0.0),)
