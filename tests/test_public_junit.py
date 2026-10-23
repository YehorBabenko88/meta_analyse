"""Synthetic negative tests for strict public JUnit profile."""
import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
P = Path(__file__).resolve().parents[1] / "scripts/check_public_junit.py"
spec = importlib.util.spec_from_file_location("public_junit", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def sample(tmp_path):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", name="suite", tests="1", errors="0", failures="0", skipped="0")
    ET.SubElement(suite, "testcase", classname="tests.test_demo", name="test_ok")
    p = tmp_path / "safe.xml"
    ET.ElementTree(root).write(p, encoding="utf-8", xml_declaration=True)
    return p

def test_safe_minimal(tmp_path):
    assert m.inspect_file(sample(tmp_path))

@pytest.mark.parametrize("kind", ["hostname", "username", "raw_failure", "system_out",
    "duplicate_case", "comment", "pi", "doctype", "extra_attribute", "missing",
    "empty_status", "nested_metadata", "wrong_counter", "nested_suite"])
def test_bad_public_junit_is_rejected(tmp_path, kind):
    p = sample(tmp_path)
    root = ET.parse(p).getroot()
    suite = root[0]
    if kind == "hostname": suite.set("hostname", "SYNTHETIC_HOST")
    elif kind == "username": suite.set("username", "SYNTHETIC_USER")
    elif kind == "raw_failure": ET.SubElement(suite[0], "failure", message="SYNTHETIC_PATH")
    elif kind == "empty_status": ET.SubElement(suite[0], "skipped")
    elif kind == "system_out": ET.SubElement(suite, "system-out").text = "SYNTHETIC_SECRET"
    elif kind == "duplicate_case":
        ET.SubElement(suite, "testcase", classname="tests.test_demo", name="test_ok"); suite.set("tests", "2")
    elif kind == "extra_attribute": suite[0].set("original-file", "SYNTHETIC_FILE")
    elif kind == "wrong_counter": suite.set("tests", "2")
    elif kind == "nested_metadata": ET.SubElement(suite, "properties")
    elif kind == "nested_suite": ET.SubElement(suite, "testsuite", name="empty", tests="0")
    elif kind == "missing": p.unlink()
    if kind in {"hostname", "username", "raw_failure", "empty_status", "system_out", "duplicate_case", "extra_attribute", "wrong_counter", "nested_metadata", "nested_suite"}:
        ET.ElementTree(root).write(p, encoding="utf-8", xml_declaration=True)
    elif kind == "comment": p.write_bytes(p.read_bytes() + b"<!-- SYNTHETIC_SECRET -->")
    elif kind == "pi": p.write_bytes(p.read_bytes() + b"<?pi synthetic?>")
    elif kind == "doctype": p.write_bytes(b"<!DOCTYPE testsuites>" + p.read_bytes())
    assert not m.inspect_file(p)
