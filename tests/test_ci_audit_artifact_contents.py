"""Pure offline tests for the four-cell artifact content gate."""
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_ci_audit_artifact_contents.py"
spec = importlib.util.spec_from_file_location("content_gate", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA = "a" * 40
TREE = "b" * 40

def make_cells(tmp_path):
    cells = {}
    for event, os_name in m.CELLS:
        directory = tmp_path / (event + "-" + os_name)
        directory.mkdir()
        source = dict(sha=SHA, expected_sha=SHA, tree_sha=TREE,
                      event=event, event_sha=SHA)
        (directory / "source-sha.json").write_text(json.dumps(source))
        root = ET.Element("testsuites", name="synthetic")
        suite = ET.SubElement(root, "testsuite", name="synthetic-identity",
                              tests="1", errors="0", failures="0", skipped="0")
        ET.SubElement(suite, "testcase", classname="tests.test_workflow_run_states",
                      name="test_success_only_exact_sha")
        ET.ElementTree(root).write(directory / "ci-audit.xml", encoding="utf-8")
        cells[(event, os_name)] = directory
    return cells

def test_positive_matrix(tmp_path):
    assert m.verify(make_cells(tmp_path), SHA, TREE, 1) == 1

@pytest.mark.parametrize("mutation", ["missing_cell", "wrong_sha", "wrong_tree", "missing_junit",
    "extra_file", "duplicate_case", "skipped", "wrong_event", "identity_mismatch", "symlink"])
def test_fail_closed(tmp_path, mutation):
    cells = make_cells(tmp_path)
    target = cells[("push", "windows")]
    source = target / "source-sha.json"
    junit = target / "ci-audit.xml"
    if mutation == "missing_cell":
        del cells[("push", "windows")]
    elif mutation in ("wrong_sha", "wrong_tree", "wrong_event"):
        d = json.loads(source.read_text())
        d[{"wrong_sha": "sha", "wrong_tree": "tree_sha", "wrong_event": "event"}[mutation]] = "c"*40 if mutation != "wrong_event" else "pull_request"
        source.write_text(json.dumps(d))
    elif mutation == "missing_junit":
        junit.unlink()
    elif mutation == "extra_file":
        (target / "private.json").write_text("secret")
    elif mutation in ("duplicate_case", "skipped", "identity_mismatch"):
        root = ET.parse(junit).getroot()
        suite = root[0]
        if mutation == "duplicate_case":
            ET.SubElement(suite, "testcase", classname="tests.test_workflow_run_states", name="test_success_only_exact_sha")
            suite.set("tests", "2")
        elif mutation == "skipped":
            suite.set("skipped", "1")
        else:
            suite[0].set("name", "test_different")
        ET.ElementTree(root).write(junit, encoding="utf-8")
    elif mutation == "symlink":
        other = tmp_path / "other"
        other.mkdir()
        cells[("push", "windows")] = other
        try:
            (tmp_path / "link").symlink_to(target, target_is_directory=True)
        except OSError:
            pytest.skip("symlink privilege unavailable on this runner")
        cells[("push", "windows")] = tmp_path / "link"
    with pytest.raises((ValueError, OSError)):
        m.verify(cells, SHA, TREE, 1)

def test_reject_duplicate_json_keys(tmp_path):
    cells = make_cells(tmp_path)
    (cells[("push", "windows")] / "source-sha.json").write_text('{"sha":"a","sha":"b"}')
    with pytest.raises(ValueError):
        m.verify(cells, SHA, TREE, 1)
