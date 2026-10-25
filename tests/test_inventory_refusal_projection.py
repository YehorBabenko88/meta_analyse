"""Offline refusal projection: real classifier summaries, synthetic host boundary."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'commissioning'))
import host_identity as h
import process_identity as p
from test_diagnostic_hardening import raw_facts
from test_process_inventory_identity import sample,ROOTS


def refused(counts=None):
    counts=counts if counts is not None else {'NATIVE_PROCESS_API_UNAVAILABLE':1}
    facts=raw_facts()
    assessment=dict(missing_process_paths=sum(counts.values()),verified_missing_process_paths=0,
        unknown_process_paths=sum(counts.values()),reason_counts=counts,results=['PRIVATE_PID_NAME_PATH'])
    facts['process_inventory']=assessment
    facts['grid'].update({k:v for k,v in assessment.items() if k!='results'})
    facts['grid'].update(coverage_complete=False,errors=['PRIVATE_HOST_SID_DSN_EXCEPTION'])
    facts['api_listeners']=[]
    return facts


@pytest.fixture
def boundary(monkeypatch,tmp_path):
    monkeypatch.setattr(h,'is_elevated',lambda:True)
    monkeypatch.setattr(h,'collector_identity',lambda *a,**kw:{'bound':'synthetic'})
    monkeypatch.setattr(h,'collect_facts',lambda:pytest.fail('REAL_COLLECTION_FORBIDDEN'))
    for name in ('save_private','dpapi','make_policy'):
        monkeypatch.setattr(h,name,lambda *a,**kw:pytest.fail('PRIVATE_PERSISTENCE_FORBIDDEN'))
    public=tmp_path/'public.json';private=tmp_path/'private.dpapi'
    monkeypatch.setattr(sys,'argv',['synthetic','diagnose','--expected-sha','a'*40,
        '--output',str(public),'--private-observation',str(private)])
    return monkeypatch,public,private


def invoke(boundary,capsys,facts):
    m,public,private=boundary
    m.setattr(h,'collect_facts',lambda:facts)
    assert h.main()==1
    output=capsys.readouterr()
    assert output.err==''
    report=json.loads(output.out)
    assert json.loads(public.read_text())==report
    assert report['status']==report['diagnostic_status']=='FAIL_CLOSED'
    assert report['reason_codes']==['INCOMPLETE_INVENTORY']
    assert not private.exists()
    for secret in ('PRIVATE_','winlogon.exe','hostname','sid','DSN','123','native_before'):
        assert secret not in output.out
    return report


@pytest.mark.parametrize('code',sorted(p.PUBLIC_PROCESS_REASONS))
def test_every_existing_allowlisted_rare_reason_count_is_safe(boundary,capsys,code):
    report=invoke(boundary,capsys,refused({code:1}))
    assert report['inventory_refusal']['reason_counts']=={code:1}
    assert report['inventory_refusal']['unknown_process_paths']==1


@pytest.mark.parametrize('code,snapshot,scm',[
    ('PROCESS_INVENTORY_COVERAGE_MISMATCH','INCOMPLETE','NO_SCM_REFUSAL'),
    ('PROCESS_INVENTORY_SCHEMA_INVALID','INCOMPLETE','NO_SCM_REFUSAL'),
    ('NATIVE_PROCESS_API_UNAVAILABLE','NO_COVERAGE_REFUSAL','NO_SCM_REFUSAL'),
    ('SERVICE_MEMBERSHIP_UNAVAILABLE','NO_COVERAGE_REFUSAL','UNRESOLVED'),
    ('SERVICE_MODULES_UNAVAILABLE','NO_COVERAGE_REFUSAL','UNRESOLVED'),
])
def test_categories_are_derived_from_existing_assessment(boundary,capsys,code,snapshot,scm):
    r=invoke(boundary,capsys,refused({code:1}))['inventory_refusal']
    assert r['process_snapshot']==snapshot
    assert r['scm_evidence']==scm
    assert r['http_sys_ownership']=='UNRESOLVED'


def test_uses_actual_assess_processes_without_reclassifying(boundary,capsys):
    row,evidence=sample(True);evidence['services_after_complete']=False
    facts=refused();assessment=p.assess_processes([dict(process=row,evidence=evidence)],ROOTS,[row['pid']])
    facts['process_inventory']=assessment
    facts['grid'].update({k:v for k,v in assessment.items() if k!='results'})
    boundary[0].setattr(p,'assess_processes',lambda *a,**kw:pytest.fail('MUST_NOT_REASSESS'))
    r=invoke(boundary,capsys,facts)['inventory_refusal']
    assert r['reason_counts']==assessment['reason_counts']
    assert r['scm_evidence']=='UNRESOLVED'


def test_coverage_penalty_is_not_a_specific_identity_refusal(boundary,capsys):
    r=invoke(boundary,capsys,refused({'PROCESS_INVENTORY_COVERAGE_MISMATCH':1}))['inventory_refusal']
    assert r['process_snapshot']=='INCOMPLETE'
    assert r['identity_evidence']=='NO_IDENTITY_REFUSAL'
    assert r['unknown_process_paths']==1


@pytest.mark.parametrize('listeners,state',[([], 'UNRESOLVED'),([{'pid':123,'path':'PRIVATE_PATH'}],'MATCH_OBSERVED'),(None,'NOT_EVALUATED')])
def test_http_sys_observation_is_separate_and_private(boundary,capsys,listeners,state):
    facts=refused()
    if listeners is not None:facts['api_listeners']=listeners
    else:facts.pop('api_listeners')
    assert invoke(boundary,capsys,facts)['inventory_refusal']['http_sys_ownership']==state


@pytest.mark.parametrize('bad',[None,[],True,1.0,float('nan'),float('inf'),-1,0,0x80000000,'PRIVATE_COUNT'])
def test_malformed_counts_are_not_reflected(boundary,capsys,bad):
    facts=refused();facts['process_inventory']['reason_counts']={'NATIVE_PROCESS_API_UNAVAILABLE':bad}
    assert invoke(boundary,capsys,facts)['inventory_refusal']=={'projection_status':'INVALID'}


@pytest.mark.parametrize('mutate',[
    lambda f:f['process_inventory'].update(reason_counts={'PRIVATE_PID_PATH_TOKEN':1}),
    lambda f:f['process_inventory'].update(reason_counts=[]),
    lambda f:f['process_inventory'].update(reason_counts={'NATIVE_PROCESS_API_UNAVAILABLE':2}),
    lambda f:f['process_inventory'].update(unknown_process_paths=True),
    lambda f:f.update(process_inventory=None),
    lambda f:f['grid'].update(reason_counts={'PRIVATE_REASON':1}),
    lambda f:f['grid'].update(unknown_process_paths=2),
])
def test_malformed_or_contradictory_assessment_is_explicitly_unavailable(boundary,capsys,mutate):
    facts=refused();mutate(facts)
    assert invoke(boundary,capsys,facts)['inventory_refusal']=={'projection_status':'INVALID'}


@pytest.mark.parametrize('code',['PROCESS_INVENTORY_SNAPSHOT_INVALID','PROCESS_SNAPSHOT_BINDING_INVALID'])
def test_snapshot_failure_before_assessment_has_no_invented_counts(boundary,capsys,code):
    m,public,private=boundary
    m.setattr(h,'collect_facts',lambda:(_ for _ in ()).throw(h.DiagnosticError(code)))
    assert h.main()==1
    r=json.loads(capsys.readouterr().out)
    assert r['reason_codes']==[code]
    assert r['inventory_refusal']['process_snapshot']=='INVALID'
    assert r['inventory_refusal']['reason_counts']=={}
    assert r['inventory_refusal']['unknown_process_paths'] is None
    assert not private.exists()
    assert json.loads(public.read_text())==r


def test_missing_assessment_is_not_zero_unresolved(boundary,capsys):
    facts=refused();facts.pop('process_inventory')
    r=invoke(boundary,capsys,facts)['inventory_refusal']
    assert r['unknown_process_paths'] is None
    assert r['reason_counts']=={}


def test_source_change_discards_projection(boundary,capsys):
    m,public,private=boundary
    m.setattr(h,'collect_facts',refused)
    identities=iter([{'bound':1},{'bound':2}]);m.setattr(h,'collector_identity',lambda *a,**kw:next(identities))
    assert h.main()==1
    r=json.loads(capsys.readouterr().out)
    assert r['reason_codes']==['COLLECTOR_SOURCE_CHANGED']
    assert 'inventory_refusal' not in r and not private.exists()


def test_existing_stale_pass_is_refused_and_never_republished(boundary,capsys):
    m,public,private=boundary
    public.write_bytes(b'{"status":"PASS_OBSERVATION_ONLY"}')
    assert h.main()==1
    r=json.loads(capsys.readouterr().out)
    assert r['status']=='FAIL_CLOSED' and 'inventory_refusal' not in r
    assert public.read_bytes()==b'{"status":"PASS_OBSERVATION_ONLY"}'
    assert not private.exists()


def test_existing_private_is_preserved_on_new_refusal(boundary,capsys):
    m,public,private=boundary;m.setattr(h,'collect_facts',refused)
    private.write_bytes(b'PRIVATE_EXISTING_AUTHORIZATION')
    assert h.main()==1
    r=json.loads(capsys.readouterr().out)
    assert r['status']=='FAIL_CLOSED' and r['inventory_refusal']['reason_counts']
    assert private.read_bytes()==b'PRIVATE_EXISTING_AUTHORIZATION'
    assert json.loads(public.read_text())==r


def test_zero_unresolved_is_not_complete_g0_or_authorization(boundary,capsys):
    r=invoke(boundary,capsys,refused({}))
    assert r['inventory_refusal']['unknown_process_paths']==0
    assert r['inventory_refusal']['reason_counts']=={}
    assert r['inventory_refusal']['http_sys_ownership']=='UNRESOLVED'


def test_snapshot_error_marker_is_projected_without_raw_errors(boundary,capsys):
    facts=refused();facts['grid']['errors'].append('Process snapshot incomplete')
    r=invoke(boundary,capsys,facts)
    assert r['inventory_refusal']['process_snapshot']=='INCOMPLETE'


def test_refusal_stdout_failure_does_not_emit_raw_exception(boundary,monkeypatch):
    boundary[0].setattr(h,'collect_facts',refused)
    monkeypatch.setattr('builtins.print',lambda *a,**k:(_ for _ in ()).throw(OSError('PRIVATE_STDOUT_PATH')))
    assert h.main()==1


def test_public_partial_write_failure_has_no_new_pass_or_private(boundary,capsys):
    m,public,private=boundary;m.setattr(h,'collect_facts',refused)
    def partial(owned,payload):
        owned.stream.write(payload[:16]);owned.stream.flush();raise OSError('PRIVATE_PATH_EXCEPTION')
    m.setattr(h.NewOutput,'write',partial)
    assert h.main()==1
    r=json.loads(capsys.readouterr().out)
    assert r['status']=='FAIL_CLOSED'
    assert b'PASS' not in public.read_bytes() and b'PRIVATE' not in public.read_bytes()
    assert not private.exists()


@pytest.mark.parametrize('failure',[OSError('PRIVATE_PATH'),ValueError('PRIVATE_EXCEPTION')])
def test_unexpected_collection_exception_stays_sanitized(boundary,capsys,failure):
    m,public,private=boundary
    m.setattr(h,'collect_facts',lambda:(_ for _ in ()).throw(failure))
    assert h.main()==1
    output=capsys.readouterr()
    assert 'PRIVATE' not in output.out+output.err
    assert json.loads(output.out)['status']=='FAIL_CLOSED' and not private.exists()


def test_child_policy_is_not_forced_or_inherited(monkeypatch):
    monkeypatch.setattr(h.platform,'system',lambda:'Windows')
    monkeypatch.setattr(h,'is_elevated',lambda:True)
    monkeypatch.setattr(h,'system_directory',lambda:Path('C:/Windows/System32'))
    monkeypatch.setenv('PSExecutionPolicyPreference','Bypass');calls=[]
    def child(command,**kw):
        calls.append((command,kw));return SimpleNamespace(returncode=1,stdout=b'PRIVATE',stderr=b'PRIVATE')
    monkeypatch.setattr(h.subprocess,'run',child)
    with pytest.raises(h.DiagnosticError,match='COLLECTOR_CHILD_BLOCKED'):h.collect_facts()
    command,kw=calls[0]
    assert '-ExecutionPolicy' not in command and '-Command' not in command and '-File' in command
    assert not any(k.casefold()=='psexecutionpolicypreference' for k in kw['env'])


def test_ci_is_exact_source_synthetic_without_native_or_pg_jobs():
    root=Path(h.__file__).resolve().parents[1]
    path=root/'.github/workflows/inventory-refusal-synthetic.yml';assert path.exists()
    text=path.read_text()
    assert 'windows-latest' in text and 'ubuntu-latest' in text
    assert 'pytest --noconftest' in text and 'python-version: \'3.12\'' in text
    assert 'scripts/record_ci_source.py' in text and '--minimum 184' in text
    assert 'path: public-evidence/' in text
    branch='parallel/adminit-minimal-refusal-20261025'
    for filename,count in [('ci.yml',3),('storage-ingestion.yml',1)]:
        assert (root/'.github/workflows'/filename).read_text().count('"'+branch+'"')==count
