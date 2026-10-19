"""Polling cadence must not mislabel normal open-interest as stale."""
import pytest
from meta_analyse.freshness import freshness_for_feed
from meta_analyse.freshness_style import freshness_colors_for_feed, FRESHNESS_COLORS

@pytest.mark.parametrize("key,age,expected",[
    ("orderbook:BTCUSDT",0,"FRESH"),
    ("orderbook:BTCUSDT",2,"DELAYED"),
    ("orderbook:BTCUSDT",10,"STALE"),
    ("open_interest:BTCUSDT",None,"UNKNOWN"),
    ("open_interest:BTCUSDT",299,"FRESH"),
    ("open_interest:BTCUSDT",359.9,"FRESH"),
    ("open_interest:BTCUSDT",360,"DELAYED"),
    ("open_interest:BTCUSDT",599.9,"DELAYED"),
    ("open_interest:BTCUSDT",600,"STALE"),
])
def test_feed_cadence_boundaries(key,age,expected):
    assert freshness_for_feed(key,age)==expected
    assert freshness_colors_for_feed(key,age)==FRESHNESS_COLORS[expected]
