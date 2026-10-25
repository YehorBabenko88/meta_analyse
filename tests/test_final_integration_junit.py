"""Exact opaque identity gate, without native or external operations."""
import copy
import hashlib
import json
import pytest
from scripts import check_final_integration_junit as gate

SHA = 'a' * 40
TREE = 'b' * 40


def identity(name):
    raw = (json.dumps(['suite', name], sort_keys=True, separators=(',', ':')) + '\n').encode()
    return 'case_' + hashlib.sha256(raw).hexdigest()


def manifest():
    return dict(schema=1, sha=SHA, tree=TREE,
                identities=sorted([identity('test_one'), identity('test_two')]),
                allowed_skips=[identity('test_two')])


def xml(second='', first='', name='test_two'):
    return (f'<testsuite><testcase classname="suite" name="test_one">{first}</testcase>'
            f'<testcase classname="suite" name="{name}">{second}</testcase></testsuite>').encode()


def test_final_exact_gate_accepts_complete_identity_and_allowed_skip():
    assert gate.check(xml(), manifest(), SHA, TREE) == 2
    assert gate.check(xml('<skipped message="private"/>'), manifest(), SHA, TREE) == 2


@pytest.mark.parametrize('fault', ['source', 'schema_bool', 'extra_key', 'duplicate', 'unsorted',
                                   'skip_outside', 'identity_type', 'missing', 'extra'])
def test_final_exact_gate_rejects_manifest_faults(fault):
    m = copy.deepcopy(manifest())
    if fault == 'source': m['sha'] = 'c' * 40
    if fault == 'schema_bool': m['schema'] = True
    if fault == 'extra_key': m['raw'] = 'PRIVATE'
    if fault == 'duplicate': m['identities'].append(m['identities'][0])
    if fault == 'unsorted': m['identities'].reverse()
    if fault == 'skip_outside': m['allowed_skips'] = ['case_' + '0' * 64]
    if fault == 'identity_type': m['identities'][0] = False
    if fault == 'missing': m['identities'] = [identity('test_two')]
    if fault == 'extra': m['identities'] = sorted(m['identities'] + [identity('test_three')])
    with pytest.raises(ValueError, match='FINAL_INTEGRATION_JUNIT_REJECTED'):
        gate.check(xml(), m, SHA, TREE)


@pytest.mark.parametrize('raw', [b'<bad', xml(name='test_one'), xml(name='test_three'),
    xml('<failure message="PRIVATE"/>'), xml('<error/>'),
    xml(first='<skipped/>'), xml('<skipped/><failure/>'),
    b'<!DOCTYPE x><testsuite/>', xml().replace(b'<testsuite>', b'<testsuite tests="99">')])
def test_final_exact_gate_rejects_invalid_xml_status_or_identity(raw):
    with pytest.raises(ValueError, match='FINAL_INTEGRATION_JUNIT_REJECTED'):
        gate.check(raw, manifest(), SHA, TREE)


def test_final_exact_gate_rejects_wrong_requested_source():
    with pytest.raises(ValueError, match='FINAL_INTEGRATION_JUNIT_REJECTED'):
        gate.check(xml(), manifest(), SHA, 'c' * 40)


def test_final_exact_cli_refusal_never_reflects_private_path(monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['check', 'PRIVATE_DSN_PATH', 'PRIVATE_HOST'])
    monkeypatch.setattr(gate.subprocess, 'check_output', lambda *a, **kw: SHA)
    def denied(*args):
        raise OSError('PRIVATE_DSN_PATH PRIVATE_HOST')
    monkeypatch.setattr(gate.public, 'read', denied)
    assert gate.main() == 1
    output = capsys.readouterr()
    assert output.out == ''
    assert output.err == 'BLOCKED: FINAL_INTEGRATION_JUNIT_REJECTED\n'
