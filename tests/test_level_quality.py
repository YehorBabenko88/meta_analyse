from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from meta_analyse.core import Candle
from meta_analyse.level_quality import verified_levels

def candle(t,h,l):
    return Candle(t,D(h),D(l),D(l),D(h))

def test_gap_prevents_level_publication():
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    report=verified_levels([candle(t,"100","90")],"H1",t,t+timedelta(hours=2))
    assert not report.verified
    assert report.levels==()
    assert report.missing==1

def test_complete_range_allows_unbroken_levels():
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    candles=[candle(t,"100","90"),candle(t+timedelta(hours=1),"99","91")]
    report=verified_levels(candles,"H1",t,t+timedelta(hours=2))
    assert report.verified
    assert any(x.price==D("100") and x.kind=="high" for x in report.levels)
