"""Adversarial checks for public CI projection; no host/native APIs."""
import importlib.util
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('public_projection', ROOT / 'scripts/project_public_ci_evidence.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

@pytest.fixture
def receipt(tmp_path, monkeypatch):
    source = dict(sha='a'*40, expected_sha='a'*40, tree_sha='b'*40, event='push', event_sha='a'*40)
    monkeypatch.setattr(p, 'provenance', lambda value: (p.source_check(value), dict(sha=value['sha'], tree=value['tree_sha'], event=value['event'], event_sha=value['event_sha'], run_id='123', run_attempt='1', job='test'))[1])
    path = tmp_path / 'source.json'
    path.write_text(json.dumps(source))
    return path

def raw(tmp_path, text):
    path = tmp_path / 'raw.xml'
    path.write_text(text)
    return path

def test_projection_strips_metadata_preserves_status(tmp_path, receipt):
    path = raw(tmp_path, '<testsuite tests="4" failures="1" errors="1" skipped="1" hostname="SECRET"><properties><property name="path" value="SECRET"/></properties><testcase classname="secret.path" name="pass"/><testcase classname="secret.path" name="failure"><failure message="SECRET">SECRET traceback</failure><system-out>SECRET</system-out></testcase><testcase classname="secret.path" name="error"><error>SECRET</error></testcase><testcase classname="secret.path" name="skip"><skipped message="SECRET"/></testcase></testsuite>')
    output = tmp_path / 'public'
    p.publish(output, receipt, [path])
    p.validate(output)
    xml = (output / 'junit-000.xml').read_bytes()
    assert b'SECRET' not in xml and b'secret.path' not in xml
    suite = ET.fromstring(xml)[0]
    assert suite.attrib == dict(name='public-ci', tests='4', failures='1', errors='1', skipped='1')
    assert all(c.get('classname') == 'public.tests' for c in suite)
    manifest = json.loads((output / 'manifest.json').read_text())
    assert str(path) not in json.dumps(manifest)
    assert len(manifest['inputs']['junit']) == 1

@pytest.mark.parametrize('xml', [
    '<!DOCTYPE testsuite [<!ENTITY x "bad">]><testsuite/>',
    '<?leak x?><testsuite/>',
    '<testsuite tests="0"><testcase classname="x" name="a"/></testsuite>',
    '<testsuite><testcase classname="x" name="a"><failure/><error/></testcase></testsuite>',
    '<testsuite><testcase classname="x" name="a"/><testcase classname="x" name="a"/></testsuite>',
    '<testsuite><testcase classname="x" name="a"><system-out><failure/></system-out></testcase></testsuite>',
    '<testsuite><testcase name="a"/></testsuite>',
    '<testsuite/>',
])
def test_reject_bad_xml(tmp_path, receipt, xml):
    with pytest.raises((ValueError, ET.ParseError)):
        p.publish(tmp_path / 'public', receipt, [raw(tmp_path, xml)])
    assert not (tmp_path / 'public').exists()
    assert not list(tmp_path.glob('.public-*'))

def test_cross_file_duplicate_rejected(tmp_path, receipt):
    path = raw(tmp_path, '<testsuite><testcase classname="x" name="a"/></testsuite>')
    with pytest.raises(ValueError):
        p.publish(tmp_path / 'public', receipt, [path, path])

def test_existing_target_preserved(tmp_path, receipt):
    target = tmp_path / 'public'
    target.mkdir()
    marker = target / 'marker'
    marker.write_text('keep')
    source = raw(tmp_path, '<testsuite><testcase classname="x" name="a"/></testsuite>')
    with pytest.raises(ValueError):
        p.publish(target, receipt, [source])
    assert marker.read_text() == 'keep'

def test_tampering_and_extra_inventory_rejected(tmp_path, receipt):
    path = raw(tmp_path, '<testsuite><testcase classname="x" name="a"/></testsuite>')
    target = tmp_path / 'public'
    p.publish(target, receipt, [path])
    (target / 'extra.log').write_text('secret')
    with pytest.raises(ValueError):
        p.validate(target)
    (target / 'extra.log').unlink()
    (target / 'junit-000.xml').write_text('<testsuite/>')
    with pytest.raises(ValueError):
        p.validate(target)

def test_replay_rejected(tmp_path, receipt, monkeypatch):
    path = raw(tmp_path, '<testsuite><testcase classname="x" name="a"/></testsuite>')
    target = tmp_path / 'public'
    p.publish(target, receipt, [path])
    original = p.provenance
    monkeypatch.setattr(p, 'provenance', lambda source: dict(original(source), run_attempt='2'))
    with pytest.raises(ValueError):
        p.validate(target)

def test_depth_and_size_rejected(tmp_path):
    with pytest.raises(ValueError):
        p.parse(('<testsuite>'*65 + '</testsuite>'*65).encode())
    path = tmp_path / 'large.xml'
    path.write_bytes(b'x' * (p.LIMIT + 1))
    with pytest.raises(ValueError):
        p.read(path)

def test_traversal_rejected(tmp_path):
    with pytest.raises(ValueError):
        p.safe_path(tmp_path / '..' / 'anything')

def test_source_strict():
    good = dict(sha='a'*40, expected_sha='a'*40, tree_sha='b'*40, event='push', event_sha='a'*40)
    p.source_check(good)
    for changed in (dict(good, hostname='secret'), dict(good, expected_sha='c'*40)):
        with pytest.raises(ValueError):
            p.source_check(changed)

def test_unmatched_glob_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['project', '--output', str(tmp_path / 'out'), '--source', 'source.json', '--junit-glob', str(tmp_path / '*.missing')])
    with pytest.raises(ValueError):
        p.main()

def test_mutation_survivor_rejected():
    with pytest.raises(ValueError):
        p.mutation_bytes(b'{"survived":1,"mutations":[]}')

def test_postgres_allowlist():
    assert json.loads(p.postgres_bytes(b'{"server_version":180001}')) == {'server_version': 180001}
    for data in (b'{"server_version":170001}', b'{"server_version":"180001"}', b'{"server_version":180001,"host":"SECRET"}', b'{"url":"SECRET"}'):
        with pytest.raises(ValueError):
            p.postgres_bytes(data)

def test_project_typed_receipts(tmp_path, receipt):
    xml = raw(tmp_path, '<testsuite><testcase classname="x" name="a"/></testsuite>')
    mutation = tmp_path / 'mutation.json'
    mutation.write_text('{"survived":0,"mutations":[]}')
    postgres = tmp_path / 'postgres.json'
    postgres.write_text('{"server_version":180001}')
    target = tmp_path / 'public'
    p.publish(target, receipt, [xml], [mutation], [postgres])
    manifest = p.validate(target)
    assert set(manifest['files']) == {'source-sha.json', 'junit-000.xml', 'mutations-000.json', 'postgres-000.json'}

def test_live_provenance_bindings(tmp_path, monkeypatch):
    source = dict(sha='a'*40, expected_sha='a'*40, tree_sha='b'*40, event='pull_request', event_sha='c'*40)
    monkeypatch.setattr(p.subprocess, 'check_output', lambda args, **kwargs: source['tree_sha'] if args[-1] == 'HEAD^{tree}' else source['sha'])
    event = tmp_path / 'event.json'
    event.write_text(json.dumps({'pull_request': {'head': {'sha': source['sha']}}}))
    env = dict(GITHUB_SHA=source['event_sha'], GITHUB_EVENT_NAME='pull_request', GITHUB_EVENT_PATH=str(event), GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1', GITHUB_JOB='unit')
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert p.provenance(source)['run_id'] == '123'
    for invalid in ('true', 'False', '0', '-1', '1.0', ''):
        monkeypatch.setenv('GITHUB_RUN_ID', invalid)
        with pytest.raises(ValueError):
            p.provenance(source)
    monkeypatch.setenv('GITHUB_RUN_ID', '123')
    monkeypatch.setenv('GITHUB_SHA', source['sha'])
    with pytest.raises(ValueError):
        p.provenance(source)
    monkeypatch.setenv('GITHUB_SHA', source['event_sha'])
    event.write_text(json.dumps({'pull_request': {'head': {'sha': 'd'*40}}}))
    with pytest.raises(ValueError):
        p.provenance(source)

def test_reparse_component_rejected(tmp_path, monkeypatch):
    from types import SimpleNamespace
    original = Path.lstat
    def fake_lstat(path):
        info = original(path)
        if path == tmp_path:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info
    monkeypatch.setattr(Path, 'lstat', fake_lstat)
    with pytest.raises(ValueError):
        p.safe_path(tmp_path / 'input.xml')


def test_repeated_identity_in_distinct_reports_allowed(tmp_path, receipt):
    first = raw(tmp_path, '<testsuite><testcase classname="x" name="a"><failure/></testcase></testsuite>')
    second = tmp_path / 'second.xml'
    second.write_bytes(first.read_bytes())
    target = tmp_path / 'public'
    p.publish(target, receipt, [first, second])
    p.validate(target)
    assert len(list(target.glob('junit-*.xml'))) == 2


@pytest.mark.parametrize('field', ['sha', 'tree_sha'])
def test_wrong_source_sha_or_tree_rejected_independently(monkeypatch, field):
    actual_sha='a'*40;actual_tree='b'*40
    good=dict(sha=actual_sha,expected_sha=actual_sha,tree_sha=actual_tree,event='push',event_sha=actual_sha)
    monkeypatch.setattr(p.subprocess,'check_output',lambda args,**kwargs:actual_tree if args[-1]=='HEAD^{tree}' else actual_sha)
    for key,value in dict(GITHUB_SHA=actual_sha,GITHUB_EVENT_NAME='push',GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1',GITHUB_JOB='unit').items():monkeypatch.setenv(key,value)
    assert p.provenance(good)['sha']==actual_sha
    changed=dict(good);changed[field]='c'*40
    if field=='sha':changed['expected_sha']='c'*40
    with pytest.raises(ValueError):p.provenance(changed)


def test_invalid_utf8_never_publishes(tmp_path,receipt):
    source=tmp_path/'invalid.xml';source.write_bytes(b'\xff')
    with pytest.raises(UnicodeError):p.publish(tmp_path/'public',receipt,[source])
    assert not (tmp_path/'public').exists()


def test_cli_refusal_does_not_echo_os_error_path(tmp_path):
    import subprocess
    result=subprocess.run([sys.executable,str(ROOT/'scripts/project_public_ci_evidence.py'),'--output',str(tmp_path/'public'),
        '--source',str(tmp_path/'SYNTHETIC_PRIVATE_SOURCE'),'--junit',str(tmp_path/'unused.xml')],capture_output=True,text=True)
    assert result.returncode==1 and result.stderr.strip()=='BLOCKED: public CI evidence rejected'
    assert 'SYNTHETIC_PRIVATE_SOURCE' not in result.stdout+result.stderr and 'Traceback' not in result.stderr


def test_input_inode_substitution_after_read_is_blocked(tmp_path,monkeypatch):
    from types import SimpleNamespace
    source=tmp_path/'synthetic.xml';source.write_bytes(b'SYNTHETIC')
    original=Path.lstat;calls=[]
    def replaced(path):
        info=original(path)
        if path==source:
            calls.append(True)
            if len(calls)>=3:
                return SimpleNamespace(st_mode=info.st_mode,st_file_attributes=getattr(info,'st_file_attributes',0),
                    st_dev=info.st_dev,st_ino=info.st_ino+1)
        return info
    monkeypatch.setattr(Path,'lstat',replaced)
    with pytest.raises(ValueError):p.read(source)
    assert len(calls)>=3
