"""Regression tests for fail-closed CI JUnit enforcement (R4/R7)."""
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_integration_junit.py"

def _check(tmp_path, statuses, *options):
    root = ET.Element("testsuite")
    for name, status in statuses:
        case = ET.SubElement(root, "testcase", classname="tests.test_integration_contract_ci", name=name)
        if status != "passed":
            ET.SubElement(case, status, message=f"synthetic {status}")
    root.set("tests", str(len(statuses)))
    report = tmp_path / "junit.xml"
    ET.ElementTree(root).write(report, encoding="unicode")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(report), "--minimum", "1", *options],
        capture_output=True, text=True, check=False,
    )

def test_integration_contract_ci_accepts_complete_suite(tmp_path):
    assert _check(tmp_path, [("contract_ok", "passed")], "--require", "contract_ok").returncode == 0

def test_integration_contract_ci_rejects_missing_required_test(tmp_path):
    assert _check(tmp_path, [("other", "passed")], "--require", "required").returncode != 0

def test_integration_contract_ci_rejects_unexpected_skip(tmp_path):
    assert _check(tmp_path, [("contract", "skipped")]).returncode != 0

def test_integration_contract_ci_allows_explicit_platform_skip(tmp_path):
    assert _check(tmp_path, [("windows_only", "skipped")], "--allow-skip", "windows_only").returncode == 0

def test_integration_contract_ci_rejects_failure_even_if_allowed_skip(tmp_path):
    assert _check(tmp_path, [("contract", "failure")], "--allow-skip", "contract").returncode != 0

def test_integration_contract_ci_rejects_error(tmp_path):
    assert _check(tmp_path, [("contract", "error")]).returncode != 0

def test_integration_contract_ci_rejects_too_few_tests(tmp_path):
    assert _check(tmp_path, [("contract", "passed")], "--minimum", "2").returncode != 0

def test_integration_contract_ci_rejects_malformed_report(tmp_path):
    report = tmp_path / "invalid.xml"
    report.write_text("<broken", encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), str(report), "--minimum", "1"], capture_output=True)
    assert result.returncode != 0

def test_integration_contract_ci_does_not_allow_substring_skip_bypass(tmp_path):
    result = _check(tmp_path, [("unsafe_windows_only_extra", "skipped")],
                    "--allow-skip", "windows_only")
    assert result.returncode != 0

def test_integration_contract_ci_allows_parametrized_case_by_exact_base_name(tmp_path):
    result = _check(tmp_path, [("windows_only[False]", "skipped")],
                    "--allow-skip", "windows_only")
    assert result.returncode == 0

def test_integration_contract_ci_requires_exact_name(tmp_path):
    assert _check(tmp_path, [("test_required_suffix", "passed")],
                  "--require-exact", "test_required").returncode != 0

def test_integration_contract_ci_accepts_exact_required_name(tmp_path):
    assert _check(tmp_path, [("test_required", "passed")],
                  "--require-exact", "test_required").returncode == 0

def test_integration_contract_ci_rejects_duplicate_testcase(tmp_path):
    result = _check(tmp_path, [("duplicate", "passed"), ("duplicate", "passed")])
    assert result.returncode != 0

def test_integration_contract_ci_rejects_declared_count_mismatch(tmp_path):
    root = ET.Element("testsuite", tests="99")
    ET.SubElement(root, "testcase", classname="tests.test_contract", name="only_one")
    report = tmp_path / "bad_count.xml"
    ET.ElementTree(root).write(report, encoding="unicode")
    result = subprocess.run([sys.executable, str(SCRIPT), str(report), "--minimum", "1"], capture_output=True)
    assert result.returncode != 0

def test_integration_contract_ci_never_allows_skipped_required_exact_test(tmp_path):
    result = _check(
        tmp_path, [("test_mandatory", "skipped")],
        "--require-exact", "test_mandatory", "--allow-skip", "test_mandatory",
    )
    assert result.returncode != 0
    assert "REQUIRED TEST SKIPPED" in result.stderr
