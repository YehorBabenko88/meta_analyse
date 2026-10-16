"""Freshness classifications use explicit, testable age boundaries."""
import math
import pytest
from meta_analyse.freshness import freshness_state

@pytest.mark.parametrize("age,expected",[
    (None,"UNKNOWN"),(-1,"UNKNOWN"),(float("nan"),"UNKNOWN"),
    (float("inf"),"UNKNOWN"),(0,"FRESH"),(1.999,"FRESH"),
    (2,"DELAYED"),(9.999,"DELAYED"),(10,"STALE"),(100,"STALE"),
])
def test_freshness_boundaries(age,expected):
    assert freshness_state(age)==expected

def test_configurable_thresholds():
    assert freshness_state(3,delayed_after=1,stale_after=4)=="DELAYED"

@pytest.mark.parametrize("delayed,stale",[(2,2),(3,2),(-1,3)])
def test_invalid_thresholds(delayed,stale):
    with pytest.raises(ValueError):
        freshness_state(1,delayed_after=delayed,stale_after=stale)
