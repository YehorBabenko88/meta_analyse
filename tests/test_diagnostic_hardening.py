"""Synthetic diagnostic evidence only; never execute the host native collector."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'commissioning'))
import host_identity as h
import process_identity as p
from test_process_inventory_identity import sample, ROOTS, filetime_iso


@pytest.mark.parametrize('fault,code', [
    ('missing-native', 'NATIVE_PROCESS_API_UNAVAILABLE'),
    ('api-denied', 'NATIVE_PROCESS_API_UNAVAILABLE'),
    ('image-denied', 'NATIVE_PROCESS_EVIDENCE_CHANGED'),
    ('image-empty', 'NATIVE_PROCESS_EVIDENCE_CHANGED'),
    ('image-invalid', 'IMAGE_PATH_INVALID'),
    ('image-change', 'IMAGE_PATH_CHANGED'),
    ('cim-name', 'CIM_IMAGE_NAME_MISMATCH'),
    ('cim-path', 'CIM_IMAGE_PATH_MISMATCH'),
    ('pid-reuse', 'PROCESS_CREATION_CHANGED'),
    ('pid-conflict', 'PROCESS_ID_CONFLICT'),
    ('hash-change', 'IMAGE_HASH_CHANGED'),
    ('unsigned-no-subject', 'IMAGE_SIGNATURE_UNVERIFIED'),
    ('publisher-missing', 'IMAGE_PUBLISHER_UNAVAILABLE'),
    ('publisher-unreviewed', 'SYSTEM_IMAGE_PUBLISHER_NOT_REVIEWED'),
    ('scm-incomplete', 'SERVICE_MEMBERSHIP_UNAVAILABLE'),
    ('scm-change', 'SERVICE_CONFIGURATION_CHANGED'),
    ('scm-pid-change', 'SERVICE_PID_CHANGED'),
    ('scm-state-change', 'SERVICE_STATE_CHANGED'),
    ('scm-rule', 'SERVICE_RULE_UNREVIEWED'),
    ('scm-pid', 'SERVICE_PID_MISMATCH'),
    ('scm-state', 'SERVICE_NOT_RUNNING'),
    ('scm-config-invalid', 'SERVICE_CONFIG_PATH_INVALID'),
    ('scm-config-mismatch', 'SERVICE_CONFIG_IMAGE_MISMATCH'),
])
def test_exact_refusal_predicate_remains_unresolved(fault, code):
    row, e = sample(service=fault.startswith('scm-'))
    if fault == 'missing-native': e['native_before'] = None
    if fault == 'api-denied': e['native_before'].update(error_stage='OPEN_PROCESS', win32_error=5)
    if fault == 'image-denied': e['native_before'].update(image_query_succeeded=False, path='', error_stage='QUERY_IMAGE', win32_error=5)
    if fault == 'image-empty': e['native_before']['path'] = ''
    if fault == 'image-invalid': e['native_before']['path'] = r'\\server\image.exe'
    if fault == 'image-change': e['native_after']['path'] = r'C:\Windows\System32\other.exe'
    if fault == 'cim-name': row['name'] = 'other.exe'
    if fault == 'cim-path': row['cim_path'] = r'C:\Windows\System32\other.exe'
    if fault == 'pid-reuse': e['native_after']['created'] += 10
    if fault == 'pid-conflict': e['native_after']['pid'] += 1
    if fault == 'hash-change': e['signature']['sha256_after'] = 'b' * 64
    if fault == 'unsigned-no-subject': e['signature'].update(status='NotSigned',subject=None)
    if fault == 'publisher-missing': e['signature']['subject']=None
    if fault == 'publisher-unreviewed': e['signature']['subject']='CN=Synthetic Unreviewed Publisher'
    if fault == 'scm-incomplete': e['services_after_complete'] = False
    if fault == 'scm-change': e['services_after'][0]['binary_path'] += ' --changed'
    if fault == 'scm-pid-change': e['services_after'][0]['pid'] += 1
    if fault == 'scm-state-change': e['services_after'][0]['state'] = 1
    for key in ('services_before', 'services_after'):
        if fault == 'scm-rule': e[key][0]['name'] = 'UnreviewedSyntheticService'
        if fault == 'scm-pid': e[key][0]['pid'] += 1
        if fault == 'scm-state': e[key][0]['state'] = 1
        if fault == 'scm-config-invalid': e[key][0]['binary_path'] = 'AMBIGUOUS PRIVATE VALUE'
        if fault == 'scm-config-mismatch': e[key][0]['binary_path'] = r'C:\Windows\System32\other.exe'
    assert p.classify_missing(row, e, ROOTS) == dict(status='UNRESOLVED', reason_code=code)


def raw_facts():
    row, e = sample()
    return dict(identity={k: 'PRIVATE_SENTINEL_' + k for k in h.IDENTITY_FIELDS},
        collector_elevated=True, os=dict(system='Windows', edition='Professional', build=26300),
        grid=dict(findings=[], errors=[], coverage_complete=True, visible_processes=1),
        process_evidence=[dict(process=row, evidence=e)], process_roots=ROOTS,
        private_inventory=dict(processes=[dict(ProcessId=row['pid'], ExecutablePath=row['cim_path'],Name=row['name'],ParentProcessId=row['parent_pid'],SessionId=row['session_id'],CreationFileTime=row['created'],CreationDate=filetime_iso(row['created']))]),
        http_sys_state='', terminal_processes=[], credential_names=[], production_dsn_names=[])


def test_dpapi_input_retains_evidence_for_replay_without_public_leak(monkeypatch, tmp_path, capsys):
    raw = raw_facts()
    monkeypatch.setattr(h, 'is_elevated', lambda: True, raising=False)
    monkeypatch.setattr(h.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(h, 'system_directory', lambda: Path('C:/Windows/System32'), raising=False)
    monkeypatch.setattr(h.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0, stdout=json.dumps(raw).encode()))
    facts = h.collect_facts()
    assert facts['private_inventory'].get('process_evidence') == raw['process_evidence']
    assert facts['private_inventory'].get('process_roots') == ROOTS
    private = facts['private_inventory']
    replay = p.assess_processes(private['process_evidence'], private['process_roots'], [123])
    assert replay == facts['process_inventory']
    public = json.dumps(h.public_report(facts, 'a'*64))
    for secret in ('PRIVATE_SENTINEL_', 'native_before', 'services_before', 'winlogon.exe', 'program_files'):
        assert secret not in public
    # Exercise the real serialization boundary, substituting only the platform encryption.
    encrypted_inputs = []
    def encrypt(data, **kw):
        encrypted_inputs.append(json.loads(data))
        return b'SYNTHETIC_CIPHERTEXT'
    monkeypatch.setattr(h, 'dpapi', encrypt)
    h.save_private(tmp_path/'private.dpapi', dict(facts=facts))
    assert encrypted_inputs[0]['facts']['private_inventory']['process_evidence'] == raw['process_evidence']
    assert b'native_before' not in (tmp_path/'private.dpapi').read_bytes()
    assert capsys.readouterr().out == ''


def test_no_elevation_blocks_before_powershell(monkeypatch):
    monkeypatch.setattr(h.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(h, 'is_elevated', lambda: False, raising=False)
    monkeypatch.setattr(h.subprocess, 'run', lambda *a, **kw: pytest.fail('PowerShell must never start'))
    with pytest.raises(ValueError, match='ELEVATED_TOKEN_REQUIRED'):
        h.collect_facts()


@pytest.mark.parametrize('value', [None, False, 1, 'true'])
def test_missing_or_unverified_elevation_cannot_pass_inventory(value):
    facts = raw_facts()
    facts['collector_elevated'] = value
    with pytest.raises(ValueError, match='ELEVATED_TOKEN_REQUIRED'):
        h.safe_inventory(facts)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def test_candidate_binding_rejects_wrong_sha_dirty_and_untracked_collector(tmp_path):
    root = tmp_path/'repo'; root.mkdir()
    git(root, 'init', '-q')
    git(root, 'config', 'user.name', 'Synthetic Test')
    git(root, 'config', 'user.email', 'test@example.invalid')
    (root/'commissioning').mkdir()
    for name in ('host_identity.py', 'process_identity.py', 'host-facts.ps1', 'process-evidence.ps1'):
        (root/'commissioning'/name).write_text('fixture')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'fixture')
    sha = git(root, 'rev-parse', 'HEAD')
    meta = h.collector_identity(sha, root=root)
    assert meta['candidate_sha'] == sha
    assert meta['version']
    assert len(meta['source_hashes']) == 4
    with pytest.raises(ValueError): h.collector_identity('0'*40, root=root)
    (root/'commissioning/host-facts.ps1').write_text('tampered')
    with pytest.raises(ValueError): h.collector_identity(sha, root=root)
    git(root, 'checkout', '--', 'commissioning/host-facts.ps1')
    (root/'commissioning/untracked.ps1').write_text('unreviewed')
    with pytest.raises(ValueError): h.collector_identity(sha, root=root)


def test_nonelevated_diagnose_emits_single_safe_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(h.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(h, 'is_elevated', lambda: False, raising=False)
    monkeypatch.setattr(h.subprocess, 'run', lambda *a, **kw: pytest.fail('No child processes permitted'))
    monkeypatch.setattr(sys, 'argv', ['guard', 'diagnose', '--expected-sha', '1'*40,
        '--output', str(tmp_path/'public.json'), '--private-observation', str(tmp_path/'observation.dpapi')])
    assert h.main() == 1
    public = json.loads(capsys.readouterr().out)
    assert public['diagnostic_status'] == 'FAIL_CLOSED'
    assert public['reason_codes'] == ['ELEVATED_TOKEN_REQUIRED']
    assert json.loads((tmp_path/'public.json').read_text()) == public
    assert not (tmp_path/'observation.dpapi').exists()


def test_observation_contains_collector_binding_only_privately(monkeypatch, tmp_path, capsys):
    facts = raw_facts()
    facts['api_listeners'] = [{}]
    # Successful synthetic facts; no native API or host identity is queried.
    meta = dict(version='synthetic-v2', candidate_sha='1'*40, source_hashes={'fixture.py':'2'*64})
    monkeypatch.setattr(h,'is_elevated',lambda:True)
    monkeypatch.setattr(h,'collector_identity',lambda *a,**kw:meta)
    monkeypatch.setattr(h,'collect_facts',lambda:facts)
    captured=[]
    monkeypatch.setattr(h,'save_private',lambda filename,value:captured.append(value))
    monkeypatch.setattr(sys,'argv',['guard','diagnose','--expected-sha','1'*40,'--output',str(tmp_path/'public.json'),'--private-observation',str(tmp_path/'observation.dpapi')])
    assert h.main()==0
    assert captured[0]['schema']==2
    assert captured[0]['collector']==dict(**meta,elevated=True)
    public=capsys.readouterr().out
    assert 'synthetic-v2' not in public
    assert 'source_hashes' not in public
    assert 'PRIVATE_SENTINEL_' not in public


def test_collector_change_during_collection_blocks_observation(monkeypatch,tmp_path,capsys):
    monkeypatch.setattr(h,'is_elevated',lambda:True)
    metas=iter([{'candidate_sha':'1'*40},{'candidate_sha':'2'*40}])
    monkeypatch.setattr(h,'collector_identity',lambda *a,**kw:next(metas))
    monkeypatch.setattr(h,'collect_facts',raw_facts)
    monkeypatch.setattr(h,'save_private',lambda *a:pytest.fail('Changed source must not be saved'))
    monkeypatch.setattr(sys,'argv',['guard','diagnose','--expected-sha','1'*40,'--output',str(tmp_path/'public.json'),'--private-observation',str(tmp_path/'observation.dpapi')])
    assert h.main()==1
    assert json.loads(capsys.readouterr().out)['reason_codes']==['COLLECTOR_SOURCE_CHANGED']


def test_ci_records_pull_request_head_instead_of_synthetic_merge(tmp_path):
    root=tmp_path/'repo';root.mkdir()
    git(root,'init','-q');git(root,'config','user.name','Synthetic Test');git(root,'config','user.email','test@example.invalid')
    (root/'fixture').write_text('fixture');git(root,'add','.');git(root,'commit','-qm','fixture')
    sha=git(root,'rev-parse','HEAD')
    event=tmp_path/'event.json';event.write_text(json.dumps({'pull_request':{'head':{'sha':sha}}}))
    script=Path(__file__).resolve().parents[1]/'scripts/record_ci_source.py'
    env=dict(os.environ,GITHUB_EVENT_NAME='pull_request',GITHUB_SHA='0'*40,GITHUB_EVENT_PATH=str(event))
    result=subprocess.run([sys.executable,str(script)],cwd=root,env=env,capture_output=True)
    assert result.returncode==0
    assert json.loads((root/'source-sha.json').read_text())['sha']==sha
    env['GITHUB_EVENT_NAME']='push'
    assert subprocess.run([sys.executable,str(script)],cwd=root,env=env,capture_output=True).returncode!=0


@pytest.mark.parametrize('content,accepted',[
    ('{"diagnostic_status":"FAIL_CLOSED","reason_codes":["IMAGE_PATH_UNAVAILABLE"]}',True),
    ('{"native_before":{"path":"SYNTHETIC_PRIVATE_PATH"}}',False),
    ('{"machine_guid":"SYNTHETIC_PRIVATE_GUID"}',False),
    ('PRIVATE_SENTINEL_must_never_be_uploaded',False),
    ('{"implementation_before":{"synthetic":"private"}}',False),
    ('{"modules_before":{"paths":["synthetic"]}}',False),
    ('{"native_format_path":"synthetic"}',False),
    ('{"kernel_before":{"pid":123}}',False),
    ('{"kernel_after":{"pid":123}}',False),
], ids=['safe','native-evidence','identity','sentinel','implementation','modules','native-format','kernel-before','kernel-after'])
def test_artifact_gate_rejects_raw_private_payload_without_echo(tmp_path,content,accepted):
    file=tmp_path/'public.json';file.write_text(content)
    script=Path(__file__).resolve().parents[1]/'scripts/check_public_diagnostic_artifacts.py'
    result=subprocess.run([sys.executable,str(script),str(file)],capture_output=True,text=True)
    assert (result.returncode==0)==accepted
    assert content not in result.stdout+result.stderr


def test_child_missing_elevation_is_not_trusted(monkeypatch):
    raw=raw_facts();raw.pop('collector_elevated')
    monkeypatch.setattr(h,'is_elevated',lambda:True)
    monkeypatch.setattr(h.platform,'system',lambda:'Windows')
    monkeypatch.setattr(h,'system_directory',lambda:Path('C:/Windows/System32'))
    monkeypatch.setattr(h.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout=json.dumps(raw).encode()))
    with pytest.raises(ValueError,match='ELEVATED_TOKEN_REQUIRED'): h.collect_facts()


def test_private_evidence_real_dpapi_roundtrip_or_platform_refusal(tmp_path):
    file=tmp_path/'synthetic.dpapi'
    payload=dict(schema=2,collector=dict(version='synthetic',candidate_sha='1'*40,elevated=True),facts=raw_facts())
    if sys.platform=='win32':
        h.save_private(file,payload)
        assert h.load_private(file)==payload
        assert b'PRIVATE_SENTINEL_' not in file.read_bytes()
        file.write_bytes(file.read_bytes()[:-16]+b'AAAA')
        with pytest.raises(ValueError): h.load_private(file)
    else:
        with pytest.raises(ValueError): h.save_private(file,payload)
        assert not file.exists()
