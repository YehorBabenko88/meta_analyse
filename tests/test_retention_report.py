from datetime import datetime, timedelta, timezone

from meta_analyse.history_retention import RetentionRecord
from meta_analyse.retention_report import summarize_retention


def test_retention_summary_counts_only_safe_candidates():
    now = datetime(2026, 10, 16, tzinfo=timezone.utc)
    old = now - timedelta(days=200)
    rows = [
        RetentionRecord("a.gz", 300, old, True, True),
        RetentionRecord("b.gz", 200, old, False, True),
        RetentionRecord("c.gz", 100, old, True, False),
    ]
    report = summarize_retention(rows, now=now)
    assert report.total_files == 3
    assert report.eligible_files == 1
    assert report.blocked_files == 2
    assert report.reclaimable_bytes == 300
    assert rows[0].path == "a.gz"
