"""Bounded copied-fixture diagnostics; production supervisor remains untouched."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess

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
