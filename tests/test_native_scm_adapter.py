"""Synthetic adapter acceptance: never collect host/native/DPAPI/PG data."""
import ast
import copy
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'commissioning'))
import host_identity as h
import process_identity as p
from test_diagnostic_hardening import raw_facts
from test_process_inventory_identity import sample,ROOTS,filetime_iso
from test_windows_service_contracts import evidence,CONTRACTS
from test_kernel_identity_evidence import missing_image


def adapter():
    assert (ROOT/'commissioning/native_scm_diagnostic.py').exists()
    return importlib.import_module('native_scm_diagnostic')


def facts(row=None,proof=None):
    if row is None:row,proof=evidence()
    f=raw_facts();f.pop('process_evidence');f.pop('process_roots')
    f['private_inventory'].update(process_evidence=[dict(process=row,evidence=proof)],process_roots=copy.deepcopy(ROOTS),
        processes=[dict(ProcessId=row['pid'],Name=row['name'],ParentProcessId=row['parent_pid'],SessionId=row['session_id'],
                        ExecutablePath=row['cim_path'],CreationFileTime=row['created'],CreationDate=filetime_iso(row['created']))])
    a=p.assess_processes(f['private_inventory']['process_evidence'],ROOTS,[row['pid']])
    f['process_inventory']=a;f['grid'].update({k:v for k,v in a.items() if k!='results'})
    f['grid'].update(coverage_complete=not bool(a['unknown_process_paths']),errors=[])
    f['api_listeners']=[]
    return f


def test_adapter_does_not_reclassify_or_persist(monkeypatch):
    a=adapter();f=facts()
    monkeypatch.setattr(p,'assess_processes',lambda *a,**k:pytest.fail('NO_REASSESSMENT'))
    monkeypatch.setattr(p,'classify_missing',lambda *a,**k:pytest.fail('NO_RECLASSIFICATION'))
    for name in ('save_private','dpapi','make_policy','collect_facts'):
        monkeypatch.setattr(h,name,lambda *a,**k:pytest.fail('PURE_PROJECTION_ONLY'))
    result=a.project(f)
    assert result['process_count']==0


@pytest.mark.parametrize('error,bucket',[(0,'NONE'),(5,'ACCESS_DENIED'),(31,'GEN_FAILURE'),(87,'INVALID_PARAMETER'),(122,'INSUFFICIENT_BUFFER'),(299,'PARTIAL_COPY'),(654321,'OTHER')])
def test_native_error_buckets_never_export_unknown_numbers(error,bucket):
    a=adapter();row,e=missing_image()
    for phase in ('before','after'):e['native_'+phase]['win32_error']=error
    r=a.project(facts(row,e))
    assert r['native']['before']['stage_counts']=={'QUERY_IMAGE':1}
    assert r['native']['after']['error_counts']=={bucket:1}
    assert str(654321) not in json.dumps(r)


@pytest.mark.parametrize('stage,error',[('OPEN_PROCESS_MODULES',5),('ENUM_MODULES',299),('MODULE_COUNT_INVALID',0),('MODULE_PATH',5),('MODULE_PATH_TRUNCATED',0),('ENUM_MODULES_AFTER',299),('MODULE_LIST_CHANGED',0),('PRIVATE_MODULE_PATH',99999)])
def test_module_failure_phase_and_privacy(stage,error):
    a=adapter();row,e=evidence();e['modules_after'].update(complete=False,error_stage=stage,win32_error=error)
    r=a.project(facts(row,e))
    assert r['modules']['after']['stage_counts']=={stage if stage!='PRIVATE_MODULE_PATH' else 'OTHER':1}
    assert 'PRIVATE_MODULE_PATH' not in json.dumps(r) and '99999' not in json.dumps(r)


@pytest.mark.parametrize('name',list(CONTRACTS))
@pytest.mark.parametrize('field,check',[('service_type','REGISTRY_TYPE_REVIEWED'),('account','REGISTRY_ACCOUNT_MATCH'),('expanded_image_path','REGISTRY_IMAGE_MATCH'),('name','CONFIG_MEMBER_MATCH')])
def test_service_configuration_subpredicates_share_original_checks(name,field,check):
    a=adapter();row,e=evidence(name)
    for phase in ('before','after'):
        e['implementation_'+phase][name][field]=16 if field=='service_type' else 'PRIVATE_WRONG_CONFIG'
    r=a.project(facts(row,e))
    assert r['configuration']['before']['checks'][check]['FAIL']==1
    assert 'PRIVATE_WRONG_CONFIG' not in json.dumps(r)


@pytest.mark.parametrize('mutate',[
    lambda f:f.update(process_inventory=None),
    lambda f:f['process_inventory'].update(results=[]),
    lambda f:f['process_inventory']['results'].append(copy.deepcopy(f['process_inventory']['results'][0])),
    lambda f:f['private_inventory']['process_evidence'][0]['process'].update(pid=True),
    lambda f:f['private_inventory']['process_evidence'][0]['evidence']['native_after'].update(created=123456789012345680),
    lambda f:f['private_inventory']['process_evidence'][0]['evidence']['modules_after'].update(created=123456789012345680),
    lambda f:f['private_inventory']['process_evidence'][0]['evidence']['modules_before'].update(pid=124),
    lambda f:f['private_inventory']['process_evidence'][0]['evidence']['native_before'].update(win32_error=False),
    lambda f:f['private_inventory']['process_evidence'][0]['evidence']['native_before'].pop('error_stage'),
    lambda f:f['private_inventory']['process_evidence'][0]['evidence'].update(modules_before=None),
    lambda f:f['private_inventory']['process_evidence'][0]['evidence']['modules_before'].update(paths='PRIVATE_PATH'),
    lambda f:f['process_inventory'].update(reason_counts={'PRIVATE_REASON':1}),
])
def test_malformed_and_reused_binding_rejects_all_diagnostics(mutate):
    a=adapter();row,e=evidence();e['modules_after']['complete']=False
    f=facts(row,e);mutate(f)
    with pytest.raises(a.AdapterError):a.project(f)


def test_missing_optional_phase_is_not_zero_or_success():
    a=adapter();row,e=missing_image();e.pop('services_before')
    r=a.project(facts(row,e))
    assert r['modules']['before']['stage_counts']=={'NOT_APPLICABLE':1}
    assert r['protection']=='NOT_COLLECTED' and r['architecture']=='NOT_COLLECTED'


def test_open_failure_has_unknown_lifetime_not_reused_or_verified():
    a=adapter();row,e=missing_image()
    for phase in ('before','after'):e['native_'+phase].update(error_stage='OPEN_PROCESS',win32_error=5,created=0,alive=False)
    r=a.project(facts(row,e))
    assert r['native']['before']['lifetime_counts']=={'NOT_OBSERVED':1}


def test_alive_and_changed_module_pairs_are_observations_not_admission():
    a=adapter();row,e=evidence()
    e['modules_after']['alive']=False
    e['modules_after']['paths'].append(r'C:\Windows\System32\synthetic.dll')
    r=a.project(facts(row,e))
    assert r['modules']['after']['alive_counts']=={'NOT_ALIVE':1}
    assert r['pair_stability']['modules']=={'DIFFERENT':1}
    assert r['later_implementation_checks']=='NOT_EVALUATED_BY_ADAPTER'


@pytest.mark.parametrize('pid,cim_name,native_name,created',[(0,'System Idle Process','',0),(4,'System','System',123456789012345670)])
def test_existing_kernel_positive_controls_are_not_schema_rejected(pid,cim_name,native_name,created):
    a=adapter();row,_=sample();row.update(pid=pid,name=cim_name,created=created,parent_pid=0,session_id=0)
    kernel=dict(pid=pid,name=native_name,created=created,parent_pid=0,session_id=0)
    f=facts(row,dict(kernel_before=kernel,kernel_after=copy.deepcopy(kernel)))
    assert f['process_inventory']['results'][0]['assessment']['status']=='VERIFIED_KERNEL'
    assert a.project(f)['process_count']==0


def test_kernel_endpoint_creation_change_is_not_hidden_by_cim_rounding():
    a=adapter();row,e=missing_image();e['kernel_after']['created']+=1
    with pytest.raises(a.AdapterError):a.project(facts(row,e))


@pytest.mark.parametrize('field',['parent_pid','session_id'])
def test_kernel_topology_mismatch_discards_all_diagnostics(field):
    a=adapter();row,e=missing_image();e['kernel_after'][field]+=1
    with pytest.raises(a.AdapterError):a.project(facts(row,e))


def test_kernel_and_native_groups_cannot_hide_one_tick_disagreement():
    a=adapter();row,e=missing_image()
    for phase in ('before','after'):e['kernel_'+phase]['created']+=1
    with pytest.raises(a.AdapterError):a.project(facts(row,e))


def test_module_only_known_times_must_match_exactly():
    a=adapter();row,e=evidence()
    for phase in ('before','after'):e['native_'+phase].update(created=0,alive=False,path='',image_query_succeeded=False,error_stage='OPEN_PROCESS',win32_error=5)
    e['modules_after']['created']+=1
    with pytest.raises(a.AdapterError):a.project(facts(row,e))


def test_consistent_one_tick_native_precision_is_allowed_against_rounded_cim():
    a=adapter();row,e=missing_image()
    for phase in ('before','after'):
        e['native_'+phase]['created']+=1;e['kernel_'+phase]['created']+=1
    assert a.project(facts(row,e))['native']['before']['lifetime_counts']=={'MATCHED':1}


@pytest.mark.parametrize('target,field,value',[
    ('native_before','created',True),('native_before','path',None),
    ('native_before','image_query_succeeded',1),('native_before','error_stage',[]),
    ('modules_before','complete',1),('modules_before','alive',1),('modules_before','win32_error',float('nan')),
])
def test_adversarial_endpoint_types_never_produce_partial_projection(target,field,value):
    a=adapter();row,e=evidence();e['modules_after']['complete']=False
    f=facts(row,e);f['private_inventory']['process_evidence'][0]['evidence'][target][field]=value
    with pytest.raises(a.AdapterError):a.project(f)


def test_raw_identifiers_and_exception_fields_never_leave_projection():
    a=adapter();row,e=evidence()
    for phase in ('before','after'):e['modules_'+phase].update(complete=False,error_stage='PRIVATE_EXCEPTION',win32_error=777777)
    f=facts(row,e);f['private_inventory']['secret']={'pid':999999,'hostname':'PRIVATE_HOST','sid':'PRIVATE_SID','dsn':'PRIVATE_DSN'}
    text=json.dumps(a.project(f))
    for value in ('PRIVATE','777777','999999','native_before','exe_path','hostname','dsn','sid'):assert value not in text


def test_shared_predicate_refactor_is_equivalent_to_frozen_pr39():
    helper=getattr(p,'service_host_configuration_checks',None);assert callable(helper)
    raw=subprocess.check_output(['git','-C',str(ROOT),'show','4a92643c00a7e4d113025e1df427d8f4850f0981:commissioning/process_identity.py'])
    node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='service_implementation_refusal')
    node.name='frozen';scope=dict(vars(p));exec(compile(ast.Module(body=[node],type_ignores=[]),'<frozen PR39>','exec'),scope)
    for name in CONTRACTS:
        for field in ('name','service_type','account','expanded_image_path'):
            for value in (None,False,16,32,'PRIVATE',''):
                row,e=evidence(name)
                for phase in ('before','after'):e['implementation_'+phase][name][field]=value
                args=(e['services_before'][0],e,ROOTS,e['native_before'])
                assert p.service_implementation_refusal(*args)==scope['frozen'](*args)


@pytest.fixture
def cli(monkeypatch,tmp_path):
    a=adapter();f=facts(*missing_image())
    monkeypatch.setattr(a,'source_binding',lambda *args:{'sha':'a'*40,'tree':'b'*40,'collector':{'bound':1}})
    monkeypatch.setattr(h,'is_elevated',lambda:True)
    monkeypatch.setattr(h,'collect_facts',lambda:f)
    for name in ('save_private','dpapi','make_policy','load_private'):
        monkeypatch.setattr(h,name,lambda *args,**kw:pytest.fail('NO_AUTHORIZATION'))
    return a,monkeypatch,tmp_path/'new.json'


def run_cli(cli,capsys):
    a,m,output=cli
    assert a.main(['--expected-sha','a'*40,'--expected-tree','b'*40,'--output',str(output)])==1
    data=capsys.readouterr();assert data.err==''
    r=json.loads(data.out);assert r['status']=='FAIL_CLOSED' and r['authorization']=='NONE'
    return r


def test_cli_is_always_closed_even_for_complete_observations(cli,capsys):
    a,m,out=cli;m.setattr(h,'collect_facts',facts)
    r=run_cli(cli,capsys)
    assert r['projection_status']=='AVAILABLE' and r['diagnostics']['process_count']==0
    assert json.loads(out.read_text())==r


def test_public_json_does_not_disclose_input_record_order(cli,capsys):
    a,m,out=cli;row,e=missing_image();f=facts(row,e)
    other=copy.deepcopy(f['private_inventory']['process_evidence'][0]);other['process']['pid']=124
    for phase in ('before','after'):
        other['evidence']['native_'+phase].update(pid=124,win32_error=5)
        other['evidence']['kernel_'+phase]['pid']=124
    f['private_inventory']['process_evidence'].append(other)
    cim=copy.deepcopy(f['private_inventory']['processes'][0]);cim['ProcessId']=124;f['private_inventory']['processes'].append(cim)
    f['grid']['visible_processes']=2
    assessment=p.assess_processes(f['private_inventory']['process_evidence'],ROOTS,[123,124])
    f['process_inventory']=assessment;f['grid'].update({k:v for k,v in assessment.items() if k!='results'})
    m.setattr(h,'collect_facts',lambda:f)
    args=['--expected-sha','a'*40,'--expected-tree','b'*40,'--output',str(out)]
    assert a.main(args)==1;first=capsys.readouterr().out
    f['private_inventory']['process_evidence'].reverse();f['private_inventory']['processes'].reverse();f['process_inventory']['results'].reverse()
    args[-1]=str(out.with_name('second.json'))
    assert a.main(args)==1;assert capsys.readouterr().out==first


def test_no_elevation_never_starts_source_or_collector(cli,capsys):
    a,m,out=cli;m.setattr(h,'is_elevated',lambda:False)
    m.setattr(a,'source_binding',lambda *a:pytest.fail('NO_SOURCE_AFTER_ELEVATION_REFUSAL'))
    m.setattr(h,'collect_facts',lambda:pytest.fail('NO_PHYSICAL_COLLECTION'))
    assert run_cli(cli,capsys)['reason_codes']==['ELEVATED_TOKEN_REQUIRED']


def test_initial_source_failure_never_collects(cli,capsys):
    a,m,out=cli
    m.setattr(a,'source_binding',lambda *a:(_ for _ in ()).throw(a.AdapterError('SOURCE_BINDING_INVALID')))
    m.setattr(h,'collect_facts',lambda:pytest.fail('NO_COLLECTION_WRONG_SOURCE'))
    assert run_cli(cli,capsys)['diagnostics'] is None


@pytest.mark.parametrize('collection_failure',[False,True])
@pytest.mark.parametrize('post_failure',['changed','exception'])
def test_source_binding_is_finally_checked_and_clears_partial_data(cli,capsys,collection_failure,post_failure):
    a,m,out=cli;calls=[]
    def binding(*args):
        calls.append(1)
        if len(calls)==2:
            if post_failure=='exception':raise ValueError('PRIVATE_PATH')
            return {'sha':'c'*40,'tree':'b'*40,'collector':{}}
        return {'sha':'a'*40,'tree':'b'*40,'collector':{}}
    m.setattr(a,'source_binding',binding)
    if collection_failure:m.setattr(h,'collect_facts',lambda:(_ for _ in ()).throw(OSError('PRIVATE_ERROR')))
    r=run_cli(cli,capsys)
    assert len(calls)==2 and r['diagnostics'] is None
    assert r['reason_codes']==['SOURCE_BINDING_INVALID']
    assert 'PRIVATE' not in json.dumps(r)


def test_invalid_arguments_do_not_echo_private_values(capsys):
    a=adapter();assert a.main(['--enrollment','PRIVATE_TOKEN'])==1
    result=capsys.readouterr();assert 'PRIVATE' not in result.out+result.err
    assert json.loads(result.out)['reason_codes']==['ARGUMENTS_INVALID']


@pytest.mark.parametrize('kind',['existing','write','close','stdout'])
def test_output_failures_never_authorize_or_leak(cli,capsys,kind):
    a,m,out=cli
    if kind=='existing':out.write_bytes(b'PRIVATE_EXISTING_PASS')
    elif kind=='stdout':m.setattr('builtins.print',lambda *a,**k:(_ for _ in ()).throw(OSError('PRIVATE_STDOUT')))
    else:
        old=h.NewOutput.close
        def fail(owned,*args):
            if kind=='close':old(owned)
            raise OSError('PRIVATE_OUTPUT')
        m.setattr(h.NewOutput,kind,fail)
    assert a.main(['--expected-sha','a'*40,'--expected-tree','b'*40,'--output',str(out)])==1
    result=capsys.readouterr();assert 'PRIVATE' not in result.out+result.err
    if kind=='existing':assert out.read_bytes()==b'PRIVATE_EXISTING_PASS'


def test_actual_git_binding_rejects_wrong_tree_sha_dirty_source(monkeypatch,tmp_path):
    a=adapter();root=tmp_path/'repo';root.mkdir();(root/'commissioning').mkdir()
    def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
    git('init','-q');git('config','user.name','Synthetic');git('config','user.email','test@example.invalid')
    for name in ('host_identity.py','process_identity.py','host-facts.ps1','process-evidence.ps1'):(root/'commissioning'/name).write_text('synthetic')
    git('add','.');git('commit','-qm','synthetic')
    monkeypatch.setattr(a,'ROOT',root)
    sha=git('rev-parse','HEAD');tree=git('rev-parse','HEAD^{tree}')
    assert a.source_binding(sha,tree)['tree']==tree
    for wrong_sha,wrong_tree in [('0'*40,tree),(sha,'0'*40)]:
        with pytest.raises(a.AdapterError):a.source_binding(wrong_sha,wrong_tree)
    (root/'commissioning/host_identity.py').write_text('changed')
    with pytest.raises(a.AdapterError):a.source_binding(sha,tree)


def test_dedicated_ci_is_exact_and_does_not_start_native_or_pg_jobs():
    path=ROOT/'.github/workflows/native-scm-adapter-synthetic.yml';assert path.exists()
    text=path.read_text()
    assert 'windows-latest' in text and 'ubuntu-latest' in text
    assert 'pytest --noconftest' in text and 'python-version: \'3.12\'' in text
    assert 'scripts/record_ci_source.py' in text and '--minimum 270' in text
    assert 'path: public-evidence/' in text
    branch='parallel/adminit-r0-r5-adapter-20261025'
    for filename,count in [('ci.yml',3),('storage-ingestion.yml',1)]:
        assert (ROOT/'.github/workflows'/filename).read_text().count('"'+branch+'"')==count
