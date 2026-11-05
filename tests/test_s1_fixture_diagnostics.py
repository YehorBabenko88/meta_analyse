"""Bounded copied-fixture diagnostics; production supervisor remains untouched."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]


def helper():
    path=ROOT/'scripts/s1_fixture_diagnostics.py'
    assert path.is_file(),'copied supervisor timeout has no bounded phase diagnostics'
    spec=importlib.util.spec_from_file_location('_s1_fixture_diagnostics',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_instrumentation_preserves_every_original_supervisor_line():
    m=helper();original=(ROOT/'scripts/Invoke-S1Precheck.ps1').read_text()
    instrumented=m.instrument_fixture(original)
    stripped=re.sub(r'(?ms)^# TEST_ONLY_FIXTURE_PROGRESS_BEGIN\n.*?^# TEST_ONLY_FIXTURE_PROGRESS_END\n','',instrumented)
    stripped=''.join(line for line in stripped.splitlines(keepends=True)if not line.strip().startswith('Fixture-Phase '))
    assert stripped==original
    for phase in ('SCRIPT_ENTERED','PACKET_DECODE','RUNTIME_FILE','ENVIRONMENT','WORKER_START',
                  'WORKER_CONTROL','WORKER_OUTPUT','RELEASE_HANDSHAKE','PUBLICATION'):
        assert "'"+phase+"'" in instrumented
    with pytest.raises(ValueError):m.instrument_fixture('unknown supervisor')


def test_missing_progress_never_infers_that_the_script_entered(tmp_path):
    m=helper();note=m.timeout_note(tmp_path)
    assert 'phase=START_NOT_OBSERVED' in note and 'reason=OUTER_15S_DEADLINE' in note


def test_valid_phase_is_bounded_and_never_contains_private_input(tmp_path):
    m=helper();path=tmp_path/'fixture-progress.json'
    path.write_text(json.dumps(dict(phase='RUNTIME_FILE',role='python_exe',elapsed_ms=1200)))
    note=m.timeout_note(tmp_path)
    assert 'phase=RUNTIME_FILE role=python_exe elapsed_ms=1200' in note
    for data in (dict(phase='PRIVATE_EXCEPTION',role='python_exe',elapsed_ms=1),
                 dict(phase='RUNTIME_FILE',role='PRIVATE_PATH',elapsed_ms=1),
                 dict(phase='RUNTIME_FILE',role='python_exe',elapsed_ms=True),
                 dict(phase='RUNTIME_FILE',role='python_exe',elapsed_ms=30001),
                 dict(phase='RUNTIME_FILE',role='python_exe',elapsed_ms=1,secret='PRIVATE_TOKEN')):
        path.write_text(json.dumps(data));note=m.timeout_note(tmp_path)
        assert 'phase=UNAVAILABLE' in note and 'PRIVATE' not in note
    for raw in ('{"phase":"SCRIPT_ENTERED","phase":"PRIVATE"}', 'PRIVATE'*100, '{'):
        path.write_text(raw);assert 'phase=UNAVAILABLE' in m.timeout_note(tmp_path)


def test_annotation_retains_original_timeout_and_only_emits_closed_diagnostics(tmp_path):
    m=helper();error=subprocess.TimeoutExpired(['PRIVATE_COMMAND','PRIVATE_PATH'],15,output=b'PRIVATE_OUTPUT')
    output=io.StringIO()
    with contextlib.redirect_stdout(output):m.annotate_timeout(tmp_path,error)
    assert error.cmd==['PRIVATE_COMMAND','PRIVATE_PATH'] and error.timeout==15 and error.output==b'PRIVATE_OUTPUT'
    assert len(error.__notes__)==1 and 'S1_FIXTURE_TIMEOUT' in error.__notes__[0]
    assert 'PRIVATE' not in output.getvalue() and str(tmp_path) not in output.getvalue()


def test_closed_projection_retains_only_trusted_failed_case_marker():
    m=helper()
    from scripts import project_public_ci_evidence as public
    note='S1_FIXTURE_TIMEOUT phase=WORKER_OUTPUT role=NONE elapsed_ms=1200 reason=OUTER_15S_DEADLINE'
    raw=('<testsuite><testcase classname="tests.test_s1_supervisor" name="test_supervisor_bounded_projection[valid]">'
         '<failure message="PRIVATE_COMMAND">PRIVATE_PATH\n'+note+'\nPRIVATE_OUTPUT</failure></testcase></testsuite>').encode()
    def inventory(data):return sorted(case.get('name')for case in public.parse(public.project(data,set())).iter('testcase'))
    expected=inventory(raw)
    lines=m.public_timeout_lines(raw,expected);assert len(lines)==1
    projected=public.parse(public.project(raw,set()))
    identity=next(projected.iter('testcase')).get('name')
    assert lines==['S1_FIXTURE_TIMEOUT case='+identity+' phase=WORKER_OUTPUT role=NONE elapsed_ms=1200 reason=OUTER_15S_DEADLINE']
    assert 'PRIVATE' not in ''.join(lines)
    unrelated=raw.replace(b'tests.test_s1_supervisor',b'tests.untrusted')
    assert m.public_timeout_lines(unrelated,inventory(unrelated))==[]
    with pytest.raises(ValueError):m.public_timeout_lines(raw,[])
    with pytest.raises(ValueError):m.public_timeout_lines(raw.replace(b'</testsuite>',raw.split(b'<testsuite>')[1]),expected)
    for payload in (b'<!DOCTYPE testsuite>'+raw,raw.replace(b'phase=WORKER_OUTPUT',b'phase=PRIVATE'),b'x'*(8*1024*1024+1)):
        with pytest.raises(ValueError):m.public_timeout_lines(payload,expected)


def test_actual_pytest_timeout_note_survives_junit_into_bounded_public_log(tmp_path):
    m=helper();tests=tmp_path/'tests';tests.mkdir();(tests/'__init__.py').write_text('')
    fixture=tests/'test_s1_supervisor.py'
    fixture.write_text("""import json,subprocess,sys
import pytest
from scripts.s1_fixture_diagnostics import annotate_timeout
@pytest.mark.parametrize('variant',['valid'])
def test_supervisor_bounded_projection(variant,tmp_path):
    (tmp_path/'fixture-progress.json').write_text(json.dumps(dict(phase='WORKER_OUTPUT',role='NONE',elapsed_ms=1)))
    try:
        subprocess.run([sys.executable,'-I','-S','-B','-c','import time;time.sleep(60)','PRIVATE_ARGUMENT'],capture_output=True,timeout=15)
    except subprocess.TimeoutExpired as error:
        annotate_timeout(tmp_path,error)
        raise
""")
    report=tmp_path/'junit.xml'
    identities=tmp_path/'source-collected-identities.json'
    environment=dict(os.environ,META_ANALYSE_SYNTHETIC_IDENTITIES=str(identities))
    code='import sys;sys.path[:0]='+repr([str(ROOT),*sys.path])+";import pytest;raise SystemExit(pytest.main(sys.argv[1:]))"
    child=subprocess.run([sys.executable,'-I','-S','-B','-c',code,'--noconftest','-p','no:cacheprovider','-p','scripts.ci_identity_manifest',
        '--rootdir',str(tmp_path),'--basetemp',str(tmp_path/'owned-pytest-temp'),'-q',str(fixture),'--junitxml',str(report)],
        capture_output=True,timeout=25,env=environment)
    assert child.returncode==1, 'negative nested fixture must remain failed'
    raw=report.read_bytes();assert b'PRIVATE_ARGUMENT' in raw
    from scripts import project_public_ci_evidence as public
    expected=json.loads(identities.read_bytes())['identities']
    lines=m.public_timeout_lines(raw,expected)
    assert len(lines)==1 and 'phase=WORKER_OUTPUT role=NONE elapsed_ms=1' in lines[0]
    assert 'PRIVATE' not in ''.join(lines) and str(tmp_path) not in ''.join(lines)
