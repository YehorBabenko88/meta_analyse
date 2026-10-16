from meta_analyse.history_progress import Availability, Segment, coverage


def test_overlap_does_not_inflate_percentage():
    rows = [
        Segment(0, 600, "bybit", Availability.AVAILABLE, True, 42),
        Segment(200, 800, "bybit", Availability.AVAILABLE, True, 12),
    ]
    progress = coverage(rows, 0, 1000)
    assert progress.percent == 80
    assert progress.verified_ms == 800
    assert progress.status == "partial"


def test_unknown_and_missing_history_never_claim_complete():
    rows = [
        Segment(0, 500, "bybit", Availability.AVAILABLE, True, 100),
        Segment(500, 1000, "bybit", Availability.UNAVAILABLE, False),
    ]
    progress = coverage(rows, 0, 1000)
    assert progress.percent == 50
    assert progress.status == "source-limited"


def test_zero_records_can_be_verified_only_with_explicit_evidence():
    rows = [Segment(0, 1000, "bybit", Availability.AVAILABLE, True, 0)]
    assert coverage(rows, 0, 1000).percent == 100
    assert coverage([Segment(0, 1000, "bybit")], 0, 1000).percent == 0


def test_unavailable_overlap_cannot_claim_green_100():
    rows = [
        Segment(0, 1000, "archive", Availability.AVAILABLE, True, 200),
        Segment(0, 1000, "exchange", Availability.UNSUPPORTED),
    ]
    progress = coverage(rows, 0, 1000)
    assert progress.status == "source-limited"
    assert progress.percent == 99
