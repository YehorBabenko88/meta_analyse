"""Fresh pure evidence/boundary tests; no collector, DPAPI or database runs."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from test_process_identity_acceptance import fixture, add_topology, ROOTS, CONTRACTS
import process_identity as p
import host_identity as h


@pytest.mark.parametrize('pid', [123.0, True, False, '123', None, [], {}, -1, 0x80000000])
def test_security_expected_pid_schema_rejects_aliases(pid):
    row, proof = fixture()
    assert p.assess_processes([dict(process=row, evidence=proof)], ROOTS, [pid])['unknown_process_paths']>0


@pytest.mark.parametrize('value', [None, {}, (), '123'])
def test_security_expected_collection_requires_list(value):
    row, proof = fixture()
    assert p.assess_processes([dict(process=row, evidence=proof)], ROOTS, value)['unknown_process_paths']>0


@pytest.mark.parametrize('value', ['missing', None, False, 0, [], {}])
def test_security_integrated_dll_absence_is_explicit_string(value):
    row, proof = fixture('SamSs')
    for key in ('implementation_before', 'implementation_after'):
        if value == 'missing': proof[key]['SamSs'].pop('expanded_dll_path')
        else: proof[key]['SamSs']['expanded_dll_path'] = value
    assert p.classify_missing(row, proof, ROOTS)['status'] == 'UNRESOLVED'


def synthetic_host(monkeypatch, pid=123, malformed_rows=False, available_path=False):
    from test_diagnostic_hardening import raw_facts
    raw = raw_facts()
    row, proof = fixture()
    raw['process_evidence'] = None if malformed_rows else [dict(process=row, evidence=proof)]
    raw['private_inventory']['processes'][0].update(ProcessId=pid,Name=row['name'],ParentProcessId=row['parent_pid'],SessionId=row['session_id'],CreationFileTime=row['created'])
    if available_path:
        raw['private_inventory']['processes'][0]['ExecutablePath'] = r'C:\Windows\System32\winlogon.exe'
        raw['process_evidence'] = []
    raw['terminal_processes'] = [dict(pid=777)]
    monkeypatch.setattr(h, 'is_elevated', lambda: True)
    monkeypatch.setattr(h.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(h, 'system_directory', lambda: Path('C:/Windows/System32'))
    monkeypatch.setattr(h, 'http_sys_owner', lambda *a: 777)
    monkeypatch.setattr(h.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0, stdout=json.dumps(raw).encode()))


@pytest.mark.parametrize('pid', [123.0, True, False, '123', None, [], {}, -1, 0x80000000])
def test_security_host_snapshot_rejects_malformed_pid(monkeypatch, pid):
    synthetic_host(monkeypatch, pid)
    with pytest.raises((h.DiagnosticError, ValueError, TypeError)):
        facts = h.collect_facts()
        h.safe_inventory(facts)


@pytest.mark.parametrize('pid', [123.0, True, False, '123', None, [], {}])
def test_security_available_path_does_not_bypass_snapshot_pid_schema(monkeypatch, pid):
    synthetic_host(monkeypatch, pid, available_path=True)
    with pytest.raises((h.DiagnosticError, ValueError, TypeError)):
        h.safe_inventory(h.collect_facts())


@pytest.mark.parametrize('bad', [None, {}, {'process': None}, {'process': {'pid': []}}, {'process': {'pid': {}}}])
def test_security_outer_exceptions_block_at_mocked_host_boundary(monkeypatch, tmp_path, capsys, bad):
    monkeypatch.setattr(h, 'is_elevated', lambda: True)
    monkeypatch.setattr(h, 'collector_identity', lambda *a, **k: dict(version='synthetic', candidate_sha='a'*40))
    monkeypatch.setattr(h, 'collect_facts', lambda: p.assess_processes([bad], ROOTS, [123]))
    monkeypatch.setattr(h, 'save_private', lambda *a, **k: pytest.fail('No private persistence on failure'))
    monkeypatch.setattr(h.subprocess, 'run', lambda *a, **k: pytest.fail('No OS subprocess'))
    monkeypatch.setattr(sys, 'argv', ['synthetic', 'diagnose', '--expected-sha', 'a'*40,
        '--output', str(tmp_path/'public.json'), '--private-observation', str(tmp_path/'never.dpapi')])
    assert h.main() == 1
    public = json.loads(capsys.readouterr().out)
    assert public['status'] == 'FAIL_CLOSED'
    assert public['reason_codes'] == ['DIAGNOSTIC_UNAVAILABLE']
    assert not (tmp_path/'never.dpapi').exists()


@pytest.mark.parametrize('name', list(CONTRACTS))
@pytest.mark.parametrize('fault', ['case-duplicate', 'nan-pid', 'infinite-created', 'module-scalar',
    'stage-nul', 'stage-whitespace', 'hash-newline', 'topology-name-change', 'after-record-null'])
def test_security_new_adversarial_variants(name, fault):
    row, proof = fixture(name)
    if fault == 'case-duplicate':
        for key in ('services_before', 'services_after'):
            proof[key].append(dict(proof[key][0], name=name.swapcase()))
    if fault == 'nan-pid': proof['services_after'][0]['pid'] = float('nan')
    if fault == 'infinite-created': proof['modules_after']['created'] = float('inf')
    if fault == 'module-scalar': proof['modules_after']['paths'] = proof['modules_after']['paths'][0]
    if fault == 'stage-nul': proof['implementation_after'][name]['error_stage'] = '\x00'
    if fault == 'stage-whitespace': proof['modules_after']['error_stage'] = ' '
    if fault == 'hash-newline': proof['signature']['sha256'] = proof['signature']['sha256_after'] = 'a'*64+'\n'
    if fault == 'topology-name-change':
        add_topology(row, proof); proof['kernel_after']['name'] = 'Registry'
    if fault == 'after-record-null': proof['services_after'] = [None]
    assert p.classify_missing(row, proof, ROOTS)['status'] == 'UNRESOLVED'


def test_security_positive_aggregate_and_host_control(monkeypatch):
    row, proof = fixture()
    assert p.assess_processes([dict(process=row, evidence=proof)], ROOTS, [123])['unknown_process_paths'] == 0
    synthetic_host(monkeypatch)
    h.safe_inventory(h.collect_facts())
