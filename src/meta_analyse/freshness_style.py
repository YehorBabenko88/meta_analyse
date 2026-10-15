"""Palette for locally observed feed freshness (not exchange latency)."""
from .freshness import freshness_state

FRESHNESS_COLORS = {
    "FRESH": ("#61D095", "#153529"),
    "DELAYED": ("#FFD166", "#45371B"),
    "STALE": ("#FF6B6B", "#48242A"),
    "UNKNOWN": ("#B5B8C5", "#30323B"),
}

def freshness_colors(age_seconds):
    return FRESHNESS_COLORS[freshness_state(age_seconds)]
