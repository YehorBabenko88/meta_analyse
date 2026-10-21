from unittest.mock import patch
from meta_analyse.feed_watchdog import FeedWatchdog

def test_watchdog_missing_and_gap_are_unverified():
    watchdog = FeedWatchdog(5)
    assert watchdog.inspect(["BTCUSDT"])[0].status == "UNVERIFIED"
    watchdog.observed("BTCUSDT")
    assert watchdog.inspect(["BTCUSDT"])[0].status == "PROVISIONAL"
    watchdog.gap(["BTCUSDT"])
    assert watchdog.inspect(["BTCUSDT"])[0].status == "UNVERIFIED"

def test_watchdog_detects_staleness():
    with patch("meta_analyse.feed_watchdog.monotonic", return_value=10.0):
        watchdog = FeedWatchdog(2)
        watchdog.observed("BTCUSDT")
    with patch("meta_analyse.feed_watchdog.monotonic", return_value=13.0):
        assert watchdog.inspect(["BTCUSDT"])[0].status == "STALE"
