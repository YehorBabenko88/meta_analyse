"""Offline negative tests for synthetic-to-physical promotion."""
import pytest
from scripts.check_ui_e2e_acceptance import classify_ui_e2e


def sample():
    return dict(status="PASS", reason="NONE", instruments=20, publication_hz=10,
                worker_stopped=True,
                loop_closed=True, render_samples=10, render_fps=10.0,
                render_p95_ms=2.0, snapshot_to_render_p95_ms=4.0,
                heartbeat_p95_ms=12.0, process_cpu_percent_one_core=50.0,
                close_event_ms=2.0, diagnostics=dict(async_errors=0, ui_errors=0,
                    thread_violations=0, stamp_overflow=0, bridge_rows=20))


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


@pytest.mark.parametrize("key,bad", [
    ("render_fps", 0), ("render_samples", True), ("render_samples", 0),
    ("close_event_ms", None), ("close_event_ms", float("nan")),
])
def test_invalid_delivery_or_shutdown_measurements_block(key, bad):
    value = sample()
    value[key] = bad
    assert classify_ui_e2e(benchmark=value) == "BLOCKED"


@pytest.mark.parametrize("counter", ["async_errors", "ui_errors", "thread_violations", "stamp_overflow"])
def test_nonzero_ui_or_worker_fault_blocks(counter):
    value = sample()
    value["diagnostics"][counter] = 1
    assert classify_ui_e2e(benchmark=value) == "BLOCKED"


@pytest.mark.parametrize("key,bad", [
    ("instruments", 1), ("instruments", None),
    ("publication_hz", 0), ("publication_hz", 100),
])
def test_wrong_benchmark_workload_blocks(key, bad):
    value = sample()
    value[key] = bad
    assert classify_ui_e2e(benchmark=value) == "BLOCKED"


def test_missing_twenty_row_delivery_blocks():
    value = sample()
    value["diagnostics"]["bridge_rows"] = 19
    assert classify_ui_e2e(benchmark=value) == "BLOCKED"
