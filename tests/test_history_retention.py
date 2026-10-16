from datetime import datetime, timedelta, timezone

import pytest

from meta_analyse.history_retention import RetentionRecord, plan_retention


NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)


def record(**kwargs):
    values = dict(path="BTCUSDT/2024-01-01.csv.gz", bytes=100,
                  created_at=NOW - timedelta(days=200),
                  derived_committed=True, source_recoverable=True)
    values.update(kwargs)
    return RetentionRecord(**values)


def test_only_recoverable_analyzed_old_data_eligible():
    decisions = plan_retention([
        record(),
        record(derived_committed=False),
        record(source_recoverable=False),
        record(protected=True),
        record(active=True),
        record(created_at=NOW - timedelta(days=1)),
    ], now=NOW)
    assert [d.eligible for d in decisions] == [True, False, False, False, False, False]
    assert sum(d.bytes_reclaimable for d in decisions) == 100


def test_no_automatic_deletion_and_invalid_age():
    assert plan_retention([record()], now=NOW)[0].reason == "eligible for manual review"
    with pytest.raises(ValueError):
        plan_retention([record()], now=NOW, min_age_days=0)


def test_naive_time_rejected():
    with pytest.raises(ValueError):
        plan_retention([record()], now=datetime(2026, 10, 16))
