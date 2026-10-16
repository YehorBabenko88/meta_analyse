"""Offline integration tests for read-only historical flow snapshots."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from meta_analyse.desktop_service import DesktopService


def service_with_stub_runtime():
    service = DesktopService(None, lambda snapshot: None)
    service.runtime = SimpleNamespace(
        symbols=[], paper=SimpleNamespace(fills=[], positions={})
    )
    return service


def test_history_snapshot_has_buckets_and_unverified_quality():
    service = service_with_stub_runtime()
    service.load_orderflow_records([
        {"timestamp_ms": 1000, "price": "100", "volume": "2", "side": "buy"},
        {"timestamp_ms": 2000, "price": "100", "volume": "1", "side": "sell"},
    ], interval_ms=1000)
    snapshot = service.snapshot()
    assert len(snapshot.orderflow_rows) == 2
    assert snapshot.orderflow_rows[0].delta == "2"
    assert snapshot.orderflow_rows[1].cumulative_delta == "1"
    assert all(row.quality == "UNVERIFIED" for row in snapshot.orderflow_rows)
    assert "UNVERIFIED" in snapshot.orderflow_status


def test_invalid_history_does_not_replace_last_snapshot():
    service = service_with_stub_runtime()
    service.load_orderflow_records([
        {"timestamp_ms": 1, "price": "10", "volume": "1", "side": "buy"}
    ], interval_ms=1000)
    before = service.snapshot().orderflow_rows
    with pytest.raises(ValueError):
        service.load_orderflow_records([
            {"timestamp_ms": 2, "price": "NaN", "volume": "1", "side": "buy"}
        ])
    assert service.snapshot().orderflow_rows == before


def test_history_limits_fail_without_partial_publication():
    service = service_with_stub_runtime()
    service.load_orderflow_records([
        {"timestamp_ms": 1, "price": "10", "volume": "1", "side": "buy"}
    ])
    before = service.snapshot().orderflow_rows
    def excessive():
        row = {"timestamp_ms": 2, "price": "10", "volume": "1", "side": "sell"}
        for _ in range(250_001):
            yield row
    with pytest.raises(ValueError, match="limit"):
        service.load_orderflow_records(excessive())
    assert service.snapshot().orderflow_rows == before
