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
