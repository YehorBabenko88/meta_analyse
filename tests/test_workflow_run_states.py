"""Offline tests for exact-SHA workflow run inventory (no GitHub/network)."""
import importlib.util
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "scripts" / "audit_workflow_run_states.py"
spec = importlib.util.spec_from_file_location("workflow_states", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA = "a" * 40

def run(name="CI", event="push", sha=SHA, status="completed", conclusion="success", id=1):
    return dict(name=name, event=event, head_sha=sha, status=status,
                conclusion=conclusion, id=id, run_number=id, run_attempt=1)

def test_success_only_exact_sha():
    assert m.audit([run(), run(sha="b" * 40, id=99)], SHA)["CI"]["push"]["state"] == "PASS"

def test_skipped_and_queued_are_blocked():
    for status, conclusion in [("completed", "skipped"), ("queued", None), ("completed", "cancelled")]:
        assert m.audit([run(status=status, conclusion=conclusion)], SHA)["CI"]["push"]["state"] == "BLOCKED"

def test_missing_event_is_not_pass():
    assert m.audit([run()], SHA)["CI"]["pull_request"]["state"] == "NOT_RUN"

def test_later_run_overrides_older_success():
    runs = [run(id=1), run(id=2, status="queued", conclusion=None)]
    assert m.audit(runs, SHA)["CI"]["push"]["state"] == "BLOCKED"

def test_no_cross_sha_promotion():
    assert m.audit([run(sha="b" * 40)], SHA)["CI"]["push"]["state"] == "NOT_RUN"

def test_api_wrapper_and_bad_shape():
    assert m.audit({"workflow_runs": [run()]}, SHA)["CI"]["push"]["state"] == "PASS"
    try:
        m.audit({"workflow_runs": {}}, SHA)
    except ValueError:
        pass
    else:
        raise AssertionError("malformed run list accepted")
