"""Freshness cell palette transitions and unknown-data fallback."""
import pytest
from meta_analyse.freshness_style import freshness_colors, FRESHNESS_COLORS

@pytest.mark.parametrize("age,state",[
    (0.0,"FRESH"),(1.99,"FRESH"),(2.0,"DELAYED"),
    (9.99,"DELAYED"),(10.0,"STALE"),(None,"UNKNOWN"),
    (float("nan"),"UNKNOWN"),
])
def test_freshness_palette_matches_state(age,state):
    assert freshness_colors(age)==FRESHNESS_COLORS[state]

def test_all_states_have_distinct_dark_theme_colors():
    assert len(set(FRESHNESS_COLORS.values()))==4
    for foreground,background in FRESHNESS_COLORS.values():
        assert foreground.startswith("#") and len(foreground)==7
        assert background.startswith("#") and len(background)==7
