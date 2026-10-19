from unittest.mock import patch
from meta_analyse.market_health import MarketHealthMonitor

def test_combined_health_requires_both_feeds():
    health=MarketHealthMonitor()
    health.execution("BTCUSDT")
    assert health.snapshot(["BTCUSDT"])[0].combined=="UNVERIFIED"
    health.book("BTCUSDT")
    assert health.snapshot(["BTCUSDT"])[0].combined=="PROVISIONAL"
    health.gap("orderbook",["BTCUSDT"])
    assert health.snapshot(["BTCUSDT"])[0].combined=="UNVERIFIED"

def test_combined_health_marks_stale_feed():
    with patch("meta_analyse.feed_watchdog.monotonic",return_value=10):
        health=MarketHealthMonitor(stale_after_seconds=2)
        health.execution("BTCUSDT")
        health.book("BTCUSDT")
    with patch("meta_analyse.feed_watchdog.monotonic",return_value=13):
        assert health.snapshot(["BTCUSDT"])[0].combined=="STALE"
