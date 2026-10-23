#!/usr/bin/env python3
"""Read-only exact-SHA GitHub Actions run gate.

Input: JSON array of GitHub Actions workflow-run objects (or API wrapper
{"workflow_runs": [...]}). Does not call GitHub, trigger workflows or change state.
A run is PASS only if status=completed, conclusion=success and SHA matches.
Skipped/queued/cancelled/missing are BLOCKED, never PASS.
"""
import argparse
import json
import sys
from pathlib import Path

GATES = ("Kernel identity offline", "CI", "Storage ingestion integration", "Commissioning PostgreSQL18")
def classify(run, sha):
    if run is None:
        return "NOT_RUN"
    if run.get("head_sha") != sha:
        return "SHA_MISMATCH"
    if run.get("status") != "completed":
        return "BLOCKED"
    return {"success": "PASS", "failure": "FAIL", "timed_out": "FAIL",
            "action_required": "BLOCKED", "cancelled": "BLOCKED",
            "skipped": "BLOCKED"}.get(run.get("conclusion"), "BLOCKED")

def audit(payload, sha):
    runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else payload
    if not isinstance(runs, list):
        raise ValueError("expected list of workflow runs")
    report = {}
    for name in GATES:
        candidates = [r for r in runs if isinstance(r, dict) and r.get("name") == name
                      and r.get("head_sha") == sha]
        by_event = {}
        for event in ("push", "pull_request"):
            matches = [r for r in candidates if r.get("event") == event]
            # Highest run id is the latest run for this exact SHA and event.
            matches.sort(key=lambda r: r.get("id", -1) if type(r.get("id")) is int else -1)
            latest = matches[-1] if matches else None
            by_event[event] = {"run_id": latest.get("id") if latest else None,
                               "state": classify(latest, sha)}
        report[name] = by_event
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-json", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    if len(args.sha) != 40 or any(c not in "0123456789abcdef" for c in args.sha):
        parser.error("--sha must be a lowercase full 40-character commit SHA")
    try:
        report = audit(json.loads(args.runs_json.read_text(encoding="utf-8")), args.sha)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("INVALID_INPUT: " + type(exc).__name__, file=sys.stderr)
        return 2
    print(json.dumps({"sha": args.sha, "gates": report}, indent=2, sort_keys=True))
    return 0 if all(v["state"] == "PASS" for events in report.values() for v in events.values()) else 1

if __name__ == "__main__":
    raise SystemExit(main())
