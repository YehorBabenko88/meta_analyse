"""Offline negative tests for synthetic-to-physical promotion."""
import pytest
from scripts.check_ui_e2e_acceptance import classify_ui_e2e


def sample():
    return dict(status="PASS", reason="NONE", worker_stopped=True,
                loop_closed=True, render_samples=10, render_fps=10.0,
                render_p95_ms=2.0, snapshot_to_render_p95_ms=4.0,
                heartbeat_p95_ms=12.0, process_cpu_percent_one_core=50.0)


def test_synthetic_pass_is_not_physical_e2e():
    assert classify_ui_e2e(benchmark=sample()) == "BLOCKED"


@pytest.mark.parametrize("key", ["public_feed_verified", "postgres_commit_readback",
                                  "ui_freshness_verified", "resource_budget_verified",
                                  "exact_source_verified"])
def test_each_missing_physical_witness_blocks(key):
    witnesses = dict.fromkeys(("public_feed_verified", "postgres_commit_readback",
        "ui_freshness_verified", "resource_budget_verified", "exact_source_verified"), True)
    witnesses[key] = False
    assert classify_ui_e2e(benchmark=sample(), **witnesses) == "BLOCKED"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, None, "1"])
def test_malformed_performance_metric_never_passes(bad):
    value = sample()
    value["render_fps"] = bad
    assert classify_ui_e2e(benchmark=value) == "BLOCKED"


def test_shutdown_incomplete_is_failure():
    value = sample()
    value["worker_stopped"] = False
    assert classify_ui_e2e(benchmark=value) == "FAIL"


def test_fail_closed_benchmark_is_failure():
    value = sample()
    value["status"] = "FAIL_CLOSED"
    value["reason"] = "NO_RENDER_SAMPLES"
    assert classify_ui_e2e(benchmark=value) == "FAIL"
