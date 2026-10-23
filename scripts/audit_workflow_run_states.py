#!/usr/bin/env python3
"""Read-only exact-SHA GitHub Actions status inventory.

Reads a GitHub Actions runs JSON export. Does not call GitHub or modify state.
Report states never promote missing, skipped, queued or cancelled runs to PASS.
Exit 0 means valid inventory produced; --require-gate enforces selected
workflow:event gates only, preventing impossible implicit all-workflow checks.
"""
import argparse
from datetime import datetime
import json
import sys
from pathlib import Path

GATES = ("Kernel identity offline", "CI", "Storage ingestion integration", "Commissioning PostgreSQL18", "CI audit synthetic")
EVENTS = ("push", "pull_request")
STATES = {"success": "PASS", "failure": "FAIL", "timed_out": "FAIL",
          "action_required": "BLOCKED", "cancelled": "BLOCKED",
          "skipped": "BLOCKED"}
CONTRACTS = {
    "CI": ("ci.yml", {"windows", "linux", "archive-pinned-contract"},
           {"windows-test-evidence", "linux-test-evidence", "archive-pinned-contract-evidence"}),
    "Kernel identity offline": ("kernel-identity-offline.yml",
        {"synthetic (ubuntu-latest)", "synthetic (windows-latest)"},
        {"synthetic-identity-ubuntu-latest", "synthetic-identity-windows-latest"}),
    "Storage ingestion integration": ("storage-ingestion.yml", {"integration"}, {"storage-ingestion-exact-source"}),
    "Commissioning PostgreSQL18": ("commissioning-postgres18.yml", {"postgres18-linux"}, {"commissioning-postgres18"}),
    "CI audit synthetic": ("ci-audit-synthetic.yml", {"audit (ubuntu-latest)", "audit (windows-latest)"},
        {"ci-audit-ubuntu-latest", "ci-audit-windows-latest"}),
}

def positive_int(value):
    return type(value) is int and value > 0

def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def invalid(_): raise ValueError("nonfinite JSON")
    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid)

def timestamp(value):
    if type(value) is not str: raise ValueError("missing timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None: raise ValueError("unbound timestamp")
    return result

def verified_metadata(run, evidence):
    """Metadata gate only: artifact contents/JUnit/privacy still need review.

    run_evidence[decimal_run_id] contains run_attempt plus unmodified jobs and
    artifacts API response objects. Fetch jobs for that specific attempt, with
    all pages; total_count must match. Never infer receipts from run success.
    """
    filename, required_jobs, required_artifacts = CONTRACTS[run['name']]
    if run['name'] == 'Commissioning PostgreSQL18' and run['event'] != 'push':
        return 'INCOMPATIBLE_WORKFLOW_EVENT'
    if run.get('path') != '.github/workflows/' + filename:
        return 'WORKFLOW_PATH_UNVERIFIED'
    if not isinstance(evidence, dict) or type(evidence.get('run_attempt')) is not int or evidence['run_attempt'] != run['run_attempt']:
        return 'ATTEMPT_EVIDENCE_MISSING'
    jobs, artifacts = evidence.get('jobs'), evidence.get('artifacts')
    for response, key in ((jobs, 'jobs'), (artifacts, 'artifacts')):
        if not isinstance(response, dict) or not isinstance(response.get(key), list):
            return 'INCOMPLETE_API_RECEIPTS'
        if type(response.get('total_count')) is not int or response['total_count'] != len(response[key]):
            return 'INCOMPLETE_API_RECEIPTS'
    names, ids = set(), set()
    for job in jobs['jobs']:
        if not isinstance(job, dict) or not positive_int(job.get('id')) or job['id'] in ids:
            return 'JOB_IDENTITY_INVALID'
        ids.add(job['id'])
        name = job.get('name')
        if type(name) is not str or name in names: return 'JOB_IDENTITY_INVALID'
        names.add(name)
        if (type(job.get('run_id')) is not int or job['run_id'] != run['id'] or
            type(job.get('run_attempt')) is not int or job['run_attempt'] != run['run_attempt'] or
            job.get('head_sha') != run['head_sha']): return 'JOB_BINDING_INVALID'
        if job.get('status') != 'completed' or job.get('conclusion') != 'success':
            return 'JOB_NOT_SUCCESSFUL'
    if names != required_jobs: return 'REQUIRED_JOBS_MISSING_OR_UNEXPECTED'
    try: started = timestamp(run.get('run_started_at'))
    except (ValueError, TypeError): return 'ATTEMPT_TIMESTAMP_MISSING'
    names, ids = set(), set()
    for artifact in artifacts['artifacts']:
        if not isinstance(artifact, dict): return 'ARTIFACT_IDENTITY_INVALID'
        name = artifact.get('name')
        if type(name) is not str or name in names or not positive_int(artifact.get('id')) or artifact['id'] in ids:
            return 'ARTIFACT_IDENTITY_INVALID'
        names.add(name); ids.add(artifact['id'])
        bound = artifact.get('workflow_run')
        if (not isinstance(bound, dict) or type(bound.get('id')) is not int or bound['id'] != run['id'] or
            bound.get('head_sha') != run['head_sha']): return 'ARTIFACT_BINDING_INVALID'
        if artifact.get('expired') is not False or not positive_int(artifact.get('size_in_bytes')):
            return 'ARTIFACT_UNAVAILABLE'
        try:
            if timestamp(artifact.get('created_at')) < started: return 'STALE_ARTIFACT'
        except (ValueError, TypeError): return 'ARTIFACT_TIMESTAMP_MISSING'
    if names != required_artifacts: return 'REQUIRED_ARTIFACTS_MISSING_OR_UNEXPECTED'
    return None

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
    if any(not isinstance(run, dict) for run in runs):
        raise ValueError('malformed outer run')
    evidence = payload.get('run_evidence', {}) if isinstance(payload, dict) else {}
    if not isinstance(evidence, dict): raise ValueError('malformed evidence map')
    report = {}
    for name in GATES:
        by_event = {}
        for event in EVENTS:
            matches = [r for r in runs if isinstance(r, dict)
                       and r.get("name") == name and r.get("head_sha") == sha
                       and r.get("event") == event]
            identities = set()
            for run in matches:
                if not all(positive_int(run.get(key)) for key in ('id', 'run_number', 'run_attempt')):
                    raise ValueError('invalid run identity')
                identity = (run['id'], run['run_attempt'])
                if identity in identities: raise ValueError('duplicate run attempt')
                identities.add(identity)
            matches.sort(key=lambda r: (r['run_number'], r['id'], r['run_attempt']))
            latest = matches[-1] if matches else None
            state = classify(latest, sha)
            reason = None
            if state == 'PASS':
                reason = verified_metadata(latest, evidence.get(str(latest['id'])))
                if reason: state = 'BLOCKED'
            by_event[event] = {"run_id": latest.get("id") if latest else None,
                               "run_attempt": latest.get('run_attempt') if latest else None,
                               "state": state, "reason": reason}
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
        if name == 'Commissioning PostgreSQL18' and event != 'push':
            parser.error('workflow does not support the requested event')
        required.append((name, event))
    try:
        report = audit(strict_json(args.runs_json.read_text(encoding="utf-8")), args.sha)
    except (OSError, ValueError, TypeError) as exc:
        print("INVALID_INPUT: " + type(exc).__name__, file=sys.stderr)
        return 2
    verdict = ("PASS" if required and all(report[n][e]["state"] == "PASS" for n, e in required)
               else "BLOCKED" if required else "INVENTORY_ONLY")
    print(json.dumps({"sha": args.sha, "gates": report, "scope": "RUN_JOB_ARTIFACT_METADATA_ONLY",
                      "required": [{"workflow": n, "event": e} for n, e in required],
                      "verdict": verdict}, indent=2, sort_keys=True))
    return 0 if verdict in ("PASS", "INVENTORY_ONLY") else 1

if __name__ == "__main__":
    raise SystemExit(main())
