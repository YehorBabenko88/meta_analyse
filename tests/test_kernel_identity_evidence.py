"""Synthetic records only: no native collector, host observation or live services."""
import copy
import pytest
from test_process_inventory_identity import sample, ROOTS
import process_identity as p


def missing_image():
    row, evidence = sample()
    for key in ('native_before', 'native_after'):
        evidence[key].update(path='', image_query_succeeded=False,
                             error_stage='QUERY_IMAGE', win32_error=31)
    snapshot = {key: row[key] for key in ('pid', 'created', 'parent_pid', 'session_id', 'name')}
    evidence.update(kernel_before=snapshot, kernel_after=copy.deepcopy(snapshot))
    evidence.pop('signature')
    return row, evidence


@pytest.mark.parametrize('name', ['Registry', 'Secure System', 'Memory Compression', 'System', 'Idle'])
@pytest.mark.parametrize('error', [5, 31, 87])
def test_labels_errors_and_subsystem_never_authorize_arbitrary_pid(name, error):
    row, e = missing_image()
    row['name'] = name
    for key in ('kernel_before', 'kernel_after'): e[key]['name'] = name
    for key in ('native_before', 'native_after'):
        e[key].update(win32_error=error, subsystem_type=0, is_kernel=True)
    assert p.classify_missing(row, e, ROOTS) == dict(status='UNRESOLVED', reason_code='IMAGE_PATH_UNAVAILABLE')


@pytest.mark.parametrize('key', ['kernel_before', 'kernel_after'])
@pytest.mark.parametrize('value', [None, {}, [], False])
def test_missing_snapshots_are_not_kernel_evidence(key, value):
    row, e = missing_image(); e[key] = value
    assert p.classify_missing(row, e, ROOTS)['reason_code'] == 'KERNEL_IDENTITY_UNAVAILABLE'


@pytest.mark.parametrize('field', ['pid', 'created', 'parent_pid', 'session_id', 'name'])
def test_changed_snapshot_rejected(field):
    row, e = missing_image()
    e['kernel_after'][field] = 'changed' if field == 'name' else e['kernel_after'][field] + 1
    assert p.classify_missing(row, e, ROOTS)['reason_code'] == 'KERNEL_IDENTITY_CONFLICT'


@pytest.mark.parametrize('field', ['pid', 'created', 'parent_pid', 'session_id'])
@pytest.mark.parametrize('value', [None, True, False, '0', 0.0, -1])
@pytest.mark.parametrize('target', ['process', 'kernel_before', 'kernel_after'])
def test_invalid_identity_types_rejected(field, value, target):
    row, e = missing_image()
    (row if target == 'process' else e[target])[field] = value
    result = p.classify_missing(row, e, ROOTS)
    assert result['status'] == 'UNRESOLVED'
    assert result['reason_code'] != 'IMAGE_PATH_UNAVAILABLE'


@pytest.mark.parametrize('field', ['pid', 'created', 'parent_pid', 'session_id', 'name'])
def test_incomplete_snapshot_rejected(field):
    row, e = missing_image()
    for key in ('kernel_before', 'kernel_after'): e[key].pop(field)
    assert p.classify_missing(row, e, ROOTS)['reason_code'] == 'KERNEL_IDENTITY_UNAVAILABLE'


@pytest.mark.parametrize('field,value', [('parent_pid', 8), ('session_id', 1), ('created', 123456789012345671), ('pid', 124)])
def test_consistent_snapshots_must_bind_to_native_and_cim(field, value):
    row, e = missing_image()
    for key in ('kernel_before', 'kernel_after'): e[key][field] = value
    assert p.classify_missing(row, e, ROOTS)['reason_code'] == 'KERNEL_IDENTITY_CONFLICT'


def test_native_snapshot_change_rejected_even_with_stable_kernel_records():
    row, e = missing_image(); e['native_after']['win32_error'] = 5
    assert p.classify_missing(row, e, ROOTS)['reason_code'] == 'NATIVE_PROCESS_EVIDENCE_CHANGED'


@pytest.mark.parametrize('field,value', [('pid', 123.0), ('win32_error', True), ('image_query_succeeded', 0), ('path', None)])
def test_native_wrong_types_rejected(field, value):
    row, e = missing_image()
    for key in ('native_before', 'native_after'): e[key][field] = value
    assert p.classify_missing(row, e, ROOTS)['reason_code'] == 'NATIVE_PROCESS_API_UNAVAILABLE'


def test_native_pid_reuse_rejected():
    row, e = missing_image(); e['native_after']['created'] += 1
    assert p.classify_missing(row, e, ROOTS)['reason_code'] == 'PROCESS_CREATION_CHANGED'


@pytest.mark.parametrize('field', ['pid', 'created', 'alive', 'path', 'image_query_succeeded', 'error_stage', 'win32_error'])
def test_missing_native_fields_rejected(field):
    row, e = missing_image()
    for key in ('native_before', 'native_after'): e[key].pop(field)
    result = p.classify_missing(row, e, ROOTS)
    assert result['status'] == 'UNRESOLVED'
    assert result['reason_code'] != 'IMAGE_PATH_UNAVAILABLE'


def test_kernel_characteristics_cannot_change_between_snapshots():
    row, e = missing_image()
    e['kernel_before']['is_subsystem'] = False
    e['kernel_after']['is_subsystem'] = True
    assert p.classify_missing(row, e, ROOTS)['reason_code'] == 'KERNEL_IDENTITY_CONFLICT'


def test_host_boundary_keeps_unproven_identity_private_and_blocks_admission(monkeypatch):
    import json
    from pathlib import Path
    from types import SimpleNamespace
    import host_identity as h
    from test_diagnostic_hardening import raw_facts
    row, e = missing_image()
    raw = raw_facts()
    raw['process_evidence'] = [dict(process=row, evidence=e)]
    monkeypatch.setattr(h, 'is_elevated', lambda: True)
    monkeypatch.setattr(h.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(h, 'system_directory', lambda: Path('C:/Windows/System32'))
    monkeypatch.setattr(h.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0, stdout=json.dumps(raw).encode()))
    facts = h.collect_facts()
    assert facts['grid']['coverage_complete'] is False
    assert facts['grid']['reason_counts'] == {'IMAGE_PATH_UNAVAILABLE': 1}
    assert facts['grid']['verified_missing_process_paths'] == 0
    with pytest.raises(ValueError): h.safe_inventory(facts)
    public = json.dumps(h.public_report(facts, 'a'*64))
    for private in ('kernel_before', 'kernel_after', 'native_before', 'parent_pid', 'session_id', 'PRIVATE_SENTINEL_'):
        assert private not in public


@pytest.mark.parametrize('pid', [0, 4])
def test_special_kernel_rule_rejects_boolean_parent_and_session(pid):
    row = dict(pid=pid, created=123456789012345670, parent_pid=False, session_id=False,
               name='System' if pid else 'System Idle Process')
    k = dict(row, name='System' if pid else '')
    assert p.classify_missing(row, dict(kernel_before=k, kernel_after=copy.deepcopy(k)), ROOTS)['status'] == 'UNRESOLVED'
