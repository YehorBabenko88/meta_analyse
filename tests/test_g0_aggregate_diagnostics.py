"""Synthetic only: child collection, elevation, DPAPI and persistence are tripwired."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'commissioning'))
import host_identity as h
from test_diagnostic_hardening import raw_facts


@pytest.fixture
def boundary(monkeypatch):
    monkeypatch.setattr(h,'is_elevated',lambda:True)
    monkeypatch.setattr(h.platform,'system',lambda:'Windows')
    monkeypatch.setattr(h,'system_directory',lambda:Path('C:/Windows/System32'))
    monkeypatch.setattr(h,'collector_identity',lambda *a,**kw:{'synthetic':'bound'})
    monkeypatch.setattr(h.subprocess,'run',lambda *a,**kw:pytest.fail('NO_NATIVE_CHILD'))
    for name in ('save_private','dpapi','make_policy','load_private','target_identity'):
        monkeypatch.setattr(h,name,lambda *a,**kw:pytest.fail('NO_PRIVATE_PERSISTENCE_OR_AUTHORIZATION'))
    return monkeypatch


def child(boundary,raw):
    boundary.setattr(h.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout=json.dumps(raw).encode()))


def run_summary(monkeypatch,tmp_path,capsys):
    output=tmp_path/'aggregate.json'
    monkeypatch.setattr(sys,'argv',['synthetic','diagnose-aggregate','--expected-sha','a'*40,'--output',str(output)])
    assert h.main()==1
    captured=capsys.readouterr()
    assert captured.err==''
    report=json.loads(captured.out)
    assert report==json.loads(output.read_text())
    assert report['status']=='FAIL_CLOSED'
    assert report['authorization']=='NONE'
    assert report['diagnostic_status']=='AGGREGATE_ONLY_NOT_AUTHORIZATION'
    assert set(p.name for p in tmp_path.iterdir())=={'aggregate.json'}
    return report


def test_aggregate_reaches_refusal_without_private_observation(boundary,tmp_path,capsys):
    raw=raw_facts();child(boundary,raw)
    r=run_summary(boundary,tmp_path,capsys)
    assert r['aggregate']['source_snapshot_status']=='VALIDATED'
    assert r['aggregate']['process_status']=='RESOLVED'
    assert r['aggregate']['unresolved_count']==0
    assert r['aggregate']['http_sys_status']=='UNRESOLVED'
    assert 'HTTP_SYS_OWNERSHIP_UNRESOLVED' in r['reason_codes']


@pytest.mark.parametrize('name',['lsass.exe','svchost.exe','Registry','Secure System','Memory Compression'])
def test_protected_labels_stay_unresolved_and_are_never_published(boundary,tmp_path,capsys,name):
    raw=raw_facts();raw['process_evidence'][0]['process']['name']=name
    raw['private_inventory']['processes'][0]['Name']=name
    child(boundary,raw)
    r=run_summary(boundary,tmp_path,capsys)
    assert r['aggregate']['unresolved_count']==1
    assert r['aggregate']['process_status']=='UNRESOLVED'
    assert name not in json.dumps(r)


def test_incomplete_snapshot_is_distinct_from_unresolved(boundary,tmp_path,capsys):
    raw=raw_facts();raw['grid']['visible_processes']=2;child(boundary,raw)
    r=run_summary(boundary,tmp_path,capsys)
    assert r['aggregate']['snapshot_status']=='INCOMPLETE'
    assert 'INCOMPLETE_INVENTORY' in r['reason_codes']


def test_scm_and_module_evidence_counts_without_names(boundary,tmp_path,capsys):
    raw=raw_facts();e=raw['process_evidence'][0]['evidence']
    e['services_after_complete']=False
    e['modules_before']={'complete':False,'error_stage':'PRIVATE_MODULE_EXCEPTION'}
    child(boundary,raw)
    r=run_summary(boundary,tmp_path,capsys)
    assert r['aggregate']['incomplete_scm_snapshots']==1
    assert r['aggregate']['incomplete_module_snapshots']==1
    assert 'PRIVATE_MODULE_EXCEPTION' not in json.dumps(r)


@pytest.mark.parametrize('bad',[None,False,1.0,[],{},'PRIVATE_PID'])
def test_malformed_pid_does_not_crash_or_leak(boundary,tmp_path,capsys,bad):
    raw=raw_facts();raw['private_inventory']['processes'][0]['ProcessId']=bad;child(boundary,raw)
    r=run_summary(boundary,tmp_path,capsys)
    assert 'PROCESS_INVENTORY_SNAPSHOT_INVALID' in r['reason_codes']
    assert r['aggregate']['process_status']=='NOT_EVALUATED'


@pytest.mark.parametrize('mutate,status',[
    (lambda r:r.update(private_inventory=None),'NOT_EVALUATED'),
    (lambda r:r.update(process_evidence=None),'NOT_EVALUATED'),
    (lambda r:r.update(grid=None),'NOT_EVALUATED'),
    (lambda r:r['grid'].update(errors='PRIVATE_ERROR'),'NOT_EVALUATED'),
    (lambda r:r['process_evidence'].append(copy.deepcopy(r['process_evidence'][0])),'UNRESOLVED'),
    (lambda r:r['private_inventory']['processes'].append(copy.deepcopy(r['private_inventory']['processes'][0])),'NOT_EVALUATED'),
    (lambda r:r['process_evidence'][0]['process'].update(created=None),'NOT_EVALUATED'),
])
def test_malformed_outer_and_binding_remain_fail_closed(boundary,tmp_path,capsys,mutate,status):
    raw=raw_facts();mutate(raw);child(boundary,raw)
    r=run_summary(boundary,tmp_path,capsys)
    assert r['aggregate']['process_status']==status
    assert 'PRIVATE_ERROR' not in json.dumps(r)


def test_http_owner_match_is_still_fail_closed(boundary,tmp_path,capsys):
    raw=raw_facts()
    raw['http_sys_state']='Request queue name: PRIVATE_QUEUE\n HTTP://127.0.0.1:17845/\n Number of active processes attached: 1\n ID: 987, image: PRIVATE_IMAGE'
    raw['terminal_processes']=[dict(pid=987,exe_path='PRIVATE_PATH',exe_sha256='b'*64,process_started='PRIVATE_TIME')]
    child(boundary,raw)
    r=run_summary(boundary,tmp_path,capsys)
    assert r['aggregate']['http_sys_status']=='MATCHED_OBSERVATION_ONLY'
    assert '987' not in json.dumps(r) and 'PRIVATE_' not in json.dumps(r)


def test_privacy_all_raw_fields_and_unknown_reason_keys(boundary,tmp_path,capsys):
    raw=raw_facts();raw['grid']['errors']=['PRIVATE_HOST_SID_DSN_TOKEN_EXCEPTION']
    raw['credential_names']=['PRIVATE_KEY'];raw['production_dsn_names']=['PRIVATE_DSN']
    raw['http_sys_state']='PRIVATE_HTTP_PATH'
    raw['private_inventory']['extra']={'PRIVATE_PID':'PRIVATE_SID'}
    child(boundary,raw)
    r=run_summary(boundary,tmp_path,capsys)
    text=json.dumps(r)
    for forbidden in ['PRIVATE_','123','winlogon','C:\\','hostname','pid','sid','dsn','exception','reason_counts']:
        assert forbidden not in text
    assert r['aggregate']['inventory_error_count']==1


@pytest.mark.parametrize('payload',[b'null',b'[]',b'{"grid":{},"grid":{}}',b'{"x":NaN}',b'\xff'])
def test_bad_json_produces_only_fixed_aggregate_failure(boundary,tmp_path,capsys,payload):
    boundary.setattr(h.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout=payload))
    r=run_summary(boundary,tmp_path,capsys)
    assert r['aggregate']['process_status']=='NOT_EVALUATED'


def test_child_launch_obeys_persisted_policy_and_never_echoes_errors(boundary,tmp_path,capsys):
    boundary.setenv('PSExecutionPolicyPreference','Bypass')
    calls=[]
    def fail(command,**kw):
        calls.append((command,kw));return SimpleNamespace(returncode=1,stdout=b'PRIVATE_CHILD',stderr=b'PRIVATE_EXCEPTION')
    boundary.setattr(h.subprocess,'run',fail)
    r=run_summary(boundary,tmp_path,capsys)
    command,kw=calls[0]
    assert '-ExecutionPolicy' not in command and 'Bypass' not in command
    assert not any(k.casefold()=='psexecutionpolicypreference' for k in kw['env'])
    assert '-File' in command and '-Command' not in command
    assert kw['capture_output'] is True
    assert r['reason_codes']==['COLLECTOR_CHILD_BLOCKED']
    assert 'PRIVATE' not in json.dumps(r)


@pytest.mark.parametrize('error',[OSError('PRIVATE_PATH'),subprocess.TimeoutExpired('PRIVATE_TOKEN',90),ValueError('PRIVATE_HOST')])
def test_aggregate_runtime_exception_privacy(boundary,tmp_path,capsys,error):
    boundary.setattr(h.subprocess,'run',lambda *a,**kw:(_ for _ in ()).throw(error))
    r=run_summary(boundary,tmp_path,capsys)
    assert 'PRIVATE' not in json.dumps(r)


def test_changed_source_blocks_even_if_inventory_would_match(boundary,tmp_path,capsys):
    child(boundary,raw_facts());metas=iter([{'bound':1},{'bound':2}])
    boundary.setattr(h,'collector_identity',lambda *a,**kw:next(metas))
    r=run_summary(boundary,tmp_path,capsys)
    assert 'COLLECTOR_SOURCE_CHANGED' in r['reason_codes']
    assert all(v=='NOT_EVALUATED' for k,v in r['aggregate'].items() if k.endswith('_status'))


@pytest.mark.parametrize('error',[h.DiagnosticError('COLLECTOR_SOURCE_UNVERIFIED'),OSError('PRIVATE_SOURCE_PATH')])
def test_source_binding_failure_discards_all_counts(boundary,tmp_path,capsys,error):
    child(boundary,raw_facts());calls=[]
    def identity(*a,**kw):
        calls.append(1)
        if len(calls)==2:raise error
        return {'synthetic':'bound'}
    boundary.setattr(h,'collector_identity',identity)
    r=run_summary(boundary,tmp_path,capsys)
    assert r['reason_codes']==['COLLECTOR_SOURCE_UNVERIFIED']
    assert all(v=='NOT_EVALUATED' if k.endswith('_status') else v is None for k,v in r['aggregate'].items())


def test_failed_collection_is_still_post_bound(boundary,tmp_path,capsys):
    metas=iter([{'bound':1},{'bound':2}])
    boundary.setattr(h,'collector_identity',lambda *a,**kw:next(metas))
    def collect(**kw):
        kw['diagnostics'].observe_raw(raw_facts())
        raise h.DiagnosticError('PROCESS_SNAPSHOT_BINDING_INVALID')
    boundary.setattr(h,'collect_facts',collect)
    r=run_summary(boundary,tmp_path,capsys)
    assert r['reason_codes']==['COLLECTOR_SOURCE_CHANGED']
    assert all(v=='NOT_EVALUATED' if k.endswith('_status') else v is None for k,v in r['aggregate'].items())


def test_no_elevation_no_child_collection(boundary,tmp_path,capsys):
    boundary.setattr(h,'is_elevated',lambda:False)
    boundary.setattr(h.subprocess,'run',lambda *a,**kw:pytest.fail('CHILD_MUST_NOT_START'))
    r=run_summary(boundary,tmp_path,capsys)
    assert r['reason_codes']==['ELEVATED_TOKEN_REQUIRED']


def test_output_collision_never_truncates_or_collects(boundary,tmp_path,capsys):
    output=tmp_path/'existing';output.write_bytes(b'PRIVATE_EXISTING')
    boundary.setattr(h,'collect_facts',lambda **kw:pytest.fail('NO_COLLECTION_AFTER_COLLISION'))
    boundary.setattr(sys,'argv',['x','diagnose-aggregate','--expected-sha','a'*40,'--output',str(output)])
    assert h.main()==1
    assert output.read_bytes()==b'PRIVATE_EXISTING'
    assert 'PRIVATE' not in capsys.readouterr().out


def test_aggregate_argument_errors_never_echo_supplied_private_values(boundary,capsys):
    boundary.setattr(sys,'argv',['x','diagnose-aggregate','--enrollment','PRIVATE_TOKEN'])
    assert h.main()==1
    output=capsys.readouterr()
    assert 'PRIVATE_TOKEN' not in output.out+output.err
    assert json.loads(output.out)['reason_codes']==['AGGREGATE_ARGUMENTS_INVALID']


def test_stdout_failure_never_emits_raw_exception(boundary,tmp_path,monkeypatch):
    child(boundary,raw_facts())
    boundary.setattr(sys,'argv',['x','diagnose-aggregate','--expected-sha','a'*40,'--output',str(tmp_path/'aggregate.json')])
    monkeypatch.setattr('builtins.print',lambda *a,**kw:(_ for _ in ()).throw(OSError('PRIVATE_STDOUT_PATH')))
    assert h.main()==1


@pytest.mark.parametrize('operation',['write','close'])
def test_output_io_refusal_never_echoes_raw_exception(boundary,tmp_path,capsys,operation):
    child(boundary,raw_facts())
    original=h.NewOutput.close
    def fail(*args):
        if operation=='close':original(*args)
        raise OSError('PRIVATE_OUTPUT_PATH')
    boundary.setattr(h.NewOutput,operation,fail)
    boundary.setattr(sys,'argv',['x','diagnose-aggregate','--expected-sha','a'*40,'--output',str(tmp_path/'aggregate.json')])
    assert h.main()==1
    result=capsys.readouterr()
    assert 'PRIVATE' not in result.out+result.err
    assert 'AGGREGATE_OUTPUT_UNAVAILABLE' in json.loads(result.out)['reason_codes']


def test_wrapper_has_separate_parameter_set_and_no_policy_override():
    text=(Path(h.__file__).with_name('collect-host.ps1')).read_text()
    assert 'diagnose-aggregate' in text and 'AggregateReasons' in text
    assert "ParameterSetName='Observe'" in text
    assert '-ExecutionPolicy' not in text
    assert '& py @arguments 2>$null' in text


def test_scm_refusal_counts_do_not_publish_dynamic_reason_keys(boundary,tmp_path,capsys):
    raw=raw_facts();child(boundary,raw)
    import process_identity
    boundary.setattr(process_identity,'assess_processes',lambda *a:dict(results=[],unknown_process_paths=2,
        reason_counts={'SERVICE_CONFIG_PATH_INVALID':1,'PRIVATE_HOST_SID_PID':1}))
    r=run_summary(boundary,tmp_path,capsys)
    assert r['aggregate']['scm_refusal_count']==1
    assert r['aggregate']['scm_status']=='UNRESOLVED'
    assert 'PRIVATE_HOST_SID_PID' not in json.dumps(r)


@pytest.mark.parametrize('code',[['PRIVATE'],{'PRIVATE':1},'PRIVATE_SID_TOKEN_EXCEPTION'])
def test_arbitrary_error_code_is_never_reflected(boundary,tmp_path,capsys,code):
    boundary.setattr(h,'collector_identity',lambda *a,**k:(_ for _ in ()).throw(h.DiagnosticError(code)))
    r=run_summary(boundary,tmp_path,capsys)
    assert r['reason_codes']==['AGGREGATE_DIAGNOSTIC_UNAVAILABLE']


@pytest.mark.parametrize('field,value',[('snapshot_status','PRIVATE_HOST'),('unresolved_count',True),('incomplete_scm_snapshots',float('nan'))])
def test_final_projection_is_allowlisted_even_if_observer_state_is_corrupt(field,value):
    from aggregate_diagnostics import AggregateDiagnostics
    d=AggregateDiagnostics();d.values[field]=value
    report=d.report();text=json.dumps(report,allow_nan=False)
    assert 'PRIVATE_HOST' not in text
    if field.endswith('_status'):assert report['aggregate'][field]=='MALFORMED'
    else:assert report['aggregate'][field] is None


def test_dedicated_ci_is_synthetic_and_full_native_pg_jobs_are_excluded():
    root=Path(h.__file__).resolve().parents[1]
    path=root/'.github/workflows/g0-aggregate-synthetic.yml'
    assert path.exists()
    text=path.read_text()
    assert 'python-version: \'3.12\'' in text and 'pytest --noconftest' in text
    assert 'windows-latest' in text and 'ubuntu-latest' in text
    assert 'scripts/record_ci_source.py' in text
    assert '--minimum 141' in text and 'path: public-evidence/' in text
    for forbidden in ('Add-Type','DPAPI','initdb','services:','host-facts.ps1 -File'):
        assert forbidden not in text
    branch='parallel/adminit-g0-aggregate-20261025'
    for filename,count in [('ci.yml',3),('storage-ingestion.yml',1)]:
        source=(root/'.github/workflows'/filename).read_text()
        assert source.count('"'+branch+'"')==count
