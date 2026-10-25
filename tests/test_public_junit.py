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
    root = ET.Element("testsuites", name="public-ci", tests="1", errors="0", failures="0", skipped="0")
    suite = ET.SubElement(root, "testsuite", name="public-ci", tests="1", errors="0", failures="0", skipped="0")
    ET.SubElement(suite, "testcase", classname="public.tests", name="case_" + "a" * 64)
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
        ET.SubElement(suite, "testcase", classname="public.tests", name="case_" + "a" * 64); suite.set("tests", "2")
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

@pytest.mark.parametrize("status,counter", [("failure", "failures"), ("error", "errors"), ("skipped", "skipped")])
def test_redacted_status_retains_result(tmp_path, status, counter):
    p = sample(tmp_path)
    root = ET.parse(p).getroot()
    ET.SubElement(root[0][0], status, message="Details omitted")
    root.set(counter, "1")
    root[0].set(counter, "1")
    ET.ElementTree(root).write(p)
    assert m.inspect_file(p)

@pytest.mark.parametrize("where,key,value", [
    (0, "name", "SYNTHETIC_SUITE"), (0, "time", "SYNTHETIC_TIME"),
    (0, "timestamp", "SYNTHETIC_TIMESTAMP"), (0, "errors", "1"),
    (0, "failures", "1"), (0, "skipped", "1"),
    (1, "classname", "SYNTHETIC_CLASS"), (1, "name", "SYNTHETIC_CASE"),
    (1, "name", "case_" + "A" * 64), (1, "time", "SYNTHETIC_TIME"),
    (2, "name", "SYNTHETIC_ROOT"), (2, "tests", "2"),
])
def test_attribute_values_are_closed(tmp_path, where, key, value):
    p = sample(tmp_path)
    root = ET.parse(p).getroot()
    node = [root[0], root[0][0], root][where]
    node.set(key, value)
    ET.ElementTree(root).write(p)
    assert not m.inspect_file(p)

@pytest.mark.parametrize("payload", [b'<testsuite xmlns="urn:synthetic"/>', b'<!--synthetic--><testsuite/>', b'<?synthetic x?><testsuite/>', b'<!DOCTYPE testsuite><testsuite/>', b'<testsuite>' * 65 + b'</testsuite>' * 65])
def test_forbidden_xml(tmp_path, payload):
    p = tmp_path / 'unsafe.xml'
    p.write_bytes(payload)
    assert not m.inspect_file(p)

def test_size_limit(tmp_path):
    p = tmp_path / 'large.xml'
    p.write_bytes(b' ' * (m.MAX_BYTES + 1))
    assert not m.inspect_file(p)

def test_reparse_ancestor_is_rejected(tmp_path, monkeypatch):
    from types import SimpleNamespace
    p = sample(tmp_path)
    original = Path.lstat
    def fake_lstat(self):
        info = original(self)
        if self == p.parent:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info
    monkeypatch.setattr(Path, 'lstat', fake_lstat)
    assert not m.inspect_file(p)

def test_symlink_is_rejected(tmp_path):
    p = sample(tmp_path)
    link = tmp_path / 'link.xml'
    try:
        link.symlink_to(p)
    except OSError:
        pytest.skip('symlink creation unavailable')
    assert not m.inspect_file(link)

@pytest.mark.parametrize('mutation', ['wrong_message', 'text', 'children', 'multiple', 'counter', 'missing_counter'])
def test_status_profile_is_closed(tmp_path, mutation):
    p = sample(tmp_path)
    root = ET.parse(p).getroot()
    status = ET.SubElement(root[0][0], 'failure', message='Details omitted')
    root.set('failures', '1')
    root[0].set('failures', '1')
    if mutation == 'wrong_message': status.set('message', 'SYNTHETIC_SECRET')
    elif mutation == 'text': status.text = 'SYNTHETIC_SECRET'
    elif mutation == 'children': ET.SubElement(status, 'synthetic')
    elif mutation == 'multiple': ET.SubElement(root[0][0], 'error', message='Details omitted')
    elif mutation == 'counter': root.set('failures', '0')
    elif mutation == 'missing_counter': del root.attrib['errors']
    ET.ElementTree(root).write(p)
    assert not m.inspect_file(p)

def test_link_attribute_is_rejected_without_link_privileges(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import stat
    p = sample(tmp_path)
    original = Path.lstat
    def fake_lstat(self):
        if self == p:
            return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
        return original(self)
    monkeypatch.setattr(Path, 'lstat', fake_lstat)
    assert not m.inspect_file(p)
