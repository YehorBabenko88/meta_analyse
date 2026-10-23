#!/usr/bin/env python3
"""Read-only exact-SHA GitHub Actions status inventory.

Reads a GitHub Actions runs JSON export. Does not call GitHub or modify state.
Report states never promote missing, skipped, queued or cancelled runs to PASS.
Exit 0 means valid inventory produced; --require-gate enforces selected
workflow:event gates only, preventing impossible implicit all-workflow checks.
"""
import argparse
import json
import sys
from pathlib import Path

GATES = ("Kernel identity offline", "CI", "Storage ingestion integration", "Commissioning PostgreSQL18")
EVENTS = ("push", "pull_request")
STATES = {"success": "PASS", "failure": "FAIL", "timed_out": "FAIL",
          "action_required": "BLOCKED", "cancelled": "BLOCKED",
          "skipped": "BLOCKED"}

def classify(run, sha):
    if run is None:
        return "NOT_RUN"
    if run.get("head_sha") != sha:
        return "SHA_MISMATCH"
    if run.get("status") != "completed":
        return "BLOCKED"
    return STATES.get(run.get("conclusion"), "BLOCKED")

def audit(payload, sha):
    runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else payload
    if not isinstance(runs, list):
        raise ValueError("expected list of workflow runs")
    report = {}
    for name in GATES:
        by_event = {}
        for event in EVENTS:
            matches = [r for r in runs if isinstance(r, dict)
                       and r.get("name") == name and r.get("head_sha") == sha
                       and r.get("event") == event]
            matches.sort(key=lambda r: (r.get("run_number", -1) if type(r.get("run_number")) is int else -1,
                                        r.get("run_attempt", -1) if type(r.get("run_attempt")) is int else -1,
                                        r.get("id", -1) if type(r.get("id")) is int else -1))
            latest = matches[-1] if matches else None
            by_event[event] = {"run_id": latest.get("id") if latest else None,
                               "state": classify(latest, sha)}
        report[name] = by_event
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-json", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--require-gate", action="append", default=[], metavar="WORKFLOW:EVENT",
                        help="Require a PASS for an explicitly selected workflow and event; repeatable")
    args = parser.parse_args()
    if len(args.sha) != 40 or any(c not in "0123456789abcdef" for c in args.sha):
        parser.error("--sha must be a lowercase full 40-character commit SHA")
    required = []
    for gate in args.require_gate:
        try:
            name, event = gate.rsplit(":", 1)
        except ValueError:
            parser.error("--require-gate must be WORKFLOW:push or WORKFLOW:pull_request")
        if name not in GATES or event not in EVENTS:
            parser.error("unknown workflow or event in --require-gate")
        required.append((name, event))
    try:
        report = audit(json.loads(args.runs_json.read_text(encoding="utf-8")), args.sha)
    except (OSError, ValueError, TypeError) as exc:
        print("INVALID_INPUT: " + type(exc).__name__, file=sys.stderr)
        return 2
    verdict = ("PASS" if required and all(report[n][e]["state"] == "PASS" for n, e in required)
               else "BLOCKED" if required else "INVENTORY_ONLY")
    print(json.dumps({"sha": args.sha, "gates": report,
                      "required": [{"workflow": n, "event": e} for n, e in required],
                      "verdict": verdict}, indent=2, sort_keys=True))
    return 0 if verdict in ("PASS", "INVENTORY_ONLY") else 1

if __name__ == "__main__":
    raise SystemExit(main())
