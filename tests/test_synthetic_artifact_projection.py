"""No raw metadata or failure payload may survive the public JUnit projection."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('projection',Path(__file__).resolve().parents[1]/'scripts/project_synthetic_artifacts.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


def test_projection_removes_metadata_parameters_and_failure_payload(tmp_path):
    path=tmp_path/'tests.xml'
    path.write_text('''<testsuites><testsuite hostname="PRIVATE_HOST"><properties><property name="user" value="PRIVATE_USER"/></properties><testcase classname="tests.test_process_identity_acceptance" name="test_acceptance_complete_service_controls[PRIVATE_PARAMETER]"><failure message="PRIVATE_MESSAGE">PRIVATE_TRACE</failure><system-out>PRIVATE_LOG</system-out></testcase></testsuite></testsuites>''',encoding='utf-8')
    p.project_junit(path);p.validate_junit(path)
    public=path.read_text()
    assert 'PRIVATE_' not in public and 'hostname' not in public and 'system-out' not in public
    assert '[sha256:' in public and 'failures="1"' in public


def test_raw_junit_cannot_pass_strict_gate(tmp_path):
    path=tmp_path/'raw.xml';path.write_text('<testsuites><testsuite hostname="raw"/></testsuites>')
    with pytest.raises(ValueError):p.validate_junit(path)


@pytest.mark.parametrize('classname,name',[('private.hostname','test_data'),('tests.test_process_identity_acceptance','PRIVATE_TEST')])
def test_unknown_case_identity_is_not_a_public_string_channel(tmp_path,classname,name):
    path=tmp_path/'raw.xml';path.write_text(f'<testsuites><testsuite><testcase classname="{classname}" name="{name}"/></testsuite></testsuites>')
    with pytest.raises(ValueError):p.project_junit(path)
