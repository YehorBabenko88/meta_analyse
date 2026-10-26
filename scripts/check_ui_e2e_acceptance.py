"""Independent offline gate: synthetic Qt PASS is not physical E2E acceptance."""
from __future__ import annotations
import math


def classify_ui_e2e(*, benchmark, public_feed_verified=False,
                    postgres_commit_readback=False, ui_freshness_verified=False,
                    resource_budget_verified=False, exact_source_verified=False):
    if not isinstance(benchmark, dict):
        return "BLOCKED"
    if benchmark.get("status") != "PASS":
        return "FAIL" if benchmark.get("status") == "FAIL_CLOSED" else "BLOCKED"
    if benchmark.get("reason") != "NONE":
        return "FAIL"
    if benchmark.get("worker_stopped") is not True or benchmark.get("loop_closed") is not True:
        return "FAIL"
    metrics = ("render_fps", "render_p95_ms", "snapshot_to_render_p95_ms",
               "heartbeat_p95_ms", "process_cpu_percent_one_core")
    if any(type(benchmark.get(key)) not in (int, float)
           or not math.isfinite(benchmark[key]) or benchmark[key] < 0 for key in metrics):
        return "BLOCKED"
    if benchmark.get("render_samples", 0) < 1:
        return "BLOCKED"
    if any(value is not True for value in (
        public_feed_verified, postgres_commit_readback, ui_freshness_verified,
        resource_budget_verified, exact_source_verified
    )):
        return "BLOCKED"
    return "E2E_EVIDENCE_COMPLETE"
