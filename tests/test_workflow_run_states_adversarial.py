"""Synthetic CI metadata negatives; no GitHub calls or host collection."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest
from test_workflow_run_states import complete_payload

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/audit_workflow_run_states.py'
spec=importlib.util.spec_from_file_location('audit_under_test',SCRIPT)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SHA='a'*40
def run(**changes):
    result=dict(id=1,name='CI',event='push',head_sha=SHA,status='completed',conclusion='success',
                run_number=1,run_attempt=1,path='.github/workflows/ci.yml',run_started_at='2026-10-23T08:00:00Z')
    result.update(changes);return result

def test_success_without_job_or_artifact_receipts_is_not_pass():
    assert m.audit([run()],SHA)['CI']['push']['state']!='PASS'

@pytest.mark.parametrize('conclusion',['skipped','cancelled',None])
def test_successful_run_cannot_hide_nonexecuted_job(conclusion):
    payload={'workflow_runs':[run()], 'run_evidence':{'1':{'run_attempt':1,
        'jobs':{'total_count':1,'jobs':[dict(id=1,run_id=1,run_attempt=1,head_sha=SHA,
               name='windows',status='completed',conclusion=conclusion)]},
        'artifacts':{'total_count':0,'artifacts':[]}}}}
    assert m.audit(payload,SHA)['CI']['push']['state']!='PASS'

def test_conflicting_duplicate_run_cannot_select_success():
    with pytest.raises(ValueError):m.audit([run(),run(status='queued',conclusion=None)],SHA)

@pytest.mark.parametrize('field,value',[('id',True),('run_number',None),('run_attempt',1.5)])
def test_malformed_latest_identity_does_not_fall_back_to_old_success(field,value):
    with pytest.raises(ValueError):m.audit([run(),run(id=2,**{field:value})] if field!='id' else [run(),run(id=value)],SHA)

@pytest.mark.parametrize('text',['{"workflow_runs":[],"workflow_runs":[]}', '{"workflow_runs":[],"x":NaN}'])
def test_cli_rejects_ambiguous_json(tmp_path,text):
    path=tmp_path/'input.json';path.write_text(text)
    result=subprocess.run([sys.executable,str(SCRIPT),'--runs-json',str(path),'--sha',SHA],capture_output=True,text=True)
    assert result.returncode==2

def test_wrong_workflow_path_cannot_impersonate_ci():
    assert m.audit([run(path='.github/workflows/untrusted.yml')],SHA)['CI']['push']['state']!='PASS'

@pytest.mark.parametrize('mutation',[
    'missing_job','skipped_job','cancelled_job','queued_job','wrong_job_sha','old_job_attempt',
    'wrong_job_run','duplicate_job','truncated_jobs','missing_artifact','expired_artifact',
    'empty_artifact','wrong_artifact_sha','wrong_artifact_run','stale_artifact','duplicate_artifact',
    'truncated_artifacts','wrong_receipt_attempt','wrong_path','missing_job_identity'])
def test_complete_positive_receipts_require_every_binding(mutation):
    payload=complete_payload([run()])
    assert m.audit(payload,SHA)['CI']['push']['state']=='PASS'
    receipt=payload['run_evidence']['1'];jobs=receipt['jobs'];artifacts=receipt['artifacts']
    if mutation=='missing_job':jobs['jobs'].pop();jobs['total_count']-=1
    elif mutation=='skipped_job':jobs['jobs'][0]['conclusion']='skipped'
    elif mutation=='cancelled_job':jobs['jobs'][0]['conclusion']='cancelled'
    elif mutation=='queued_job':jobs['jobs'][0]['status']='queued'
    elif mutation=='wrong_job_sha':jobs['jobs'][0]['head_sha']='b'*40
    elif mutation=='old_job_attempt':jobs['jobs'][0]['run_attempt']=2
    elif mutation=='wrong_job_run':jobs['jobs'][0]['run_id']=2
    elif mutation=='duplicate_job':jobs['jobs'][1]=jobs['jobs'][0]
    elif mutation=='truncated_jobs':jobs['total_count']+=1
    elif mutation=='missing_artifact':artifacts['artifacts'].pop();artifacts['total_count']-=1
    elif mutation=='expired_artifact':artifacts['artifacts'][0]['expired']=True
    elif mutation=='empty_artifact':artifacts['artifacts'][0]['size_in_bytes']=0
    elif mutation=='wrong_artifact_sha':artifacts['artifacts'][0]['workflow_run']['head_sha']='b'*40
    elif mutation=='wrong_artifact_run':artifacts['artifacts'][0]['workflow_run']['id']=2
    elif mutation=='stale_artifact':artifacts['artifacts'][0]['created_at']='2026-10-23T07:00:00Z'
    elif mutation=='duplicate_artifact':artifacts['artifacts'][1]=artifacts['artifacts'][0]
    elif mutation=='truncated_artifacts':artifacts['total_count']+=1
    elif mutation=='wrong_receipt_attempt':receipt['run_attempt']=2
    elif mutation=='wrong_path':payload['workflow_runs'][0]['path']='.github/workflows/other.yml'
    elif mutation=='missing_job_identity':del jobs['jobs'][0]['id']
    assert m.audit(payload,SHA)['CI']['push']['state']=='BLOCKED'

def test_rerun_attempt_never_reuses_old_success_receipts():
    older=run();newer=run(run_attempt=2,status='queued',conclusion=None)
    payload=complete_payload([older]);payload['workflow_runs']=[newer,older]
    assert m.audit(payload,SHA)['CI']['push']['run_attempt']==2
    assert m.audit(payload,SHA)['CI']['push']['state']=='BLOCKED'
    newer.update(status='completed',conclusion='success')
    assert m.audit(payload,SHA)['CI']['push']['state']=='BLOCKED'

@pytest.mark.parametrize('status,conclusion', [('queued',None),('completed','skipped'),('completed','cancelled'),('completed','neutral'),('waiting',None)])
def test_nonpass_states_cannot_be_promoted_by_good_receipts(status,conclusion):
    payload=complete_payload([run(status=status,conclusion=conclusion)])
    assert m.audit(payload,SHA)['CI']['push']['state']=='BLOCKED'

def test_cli_rejects_incompatible_postgres_pull_request_gate(tmp_path):
    path=tmp_path/'input.json';path.write_text('[]')
    result=subprocess.run([sys.executable,str(SCRIPT),'--runs-json',str(path),'--sha',SHA,
        '--require-gate','Commissioning PostgreSQL18:pull_request'],capture_output=True,text=True)
    assert result.returncode==2

@pytest.mark.parametrize('sha',['a'*39,'a'*41,'A'*40,'main'])
def test_cli_requires_exact_lowercase_sha(tmp_path,sha):
    path=tmp_path/'input.json';path.write_text('[]')
    result=subprocess.run([sys.executable,str(SCRIPT),'--runs-json',str(path),'--sha',sha],capture_output=True,text=True)
    assert result.returncode==2

@pytest.mark.parametrize('name',list(m.CONTRACTS))
def test_positive_metadata_for_every_workflow_contract(name):
    value=run(name=name,path='.github/workflows/'+m.CONTRACTS[name][0])
    payload=complete_payload([value]);receipt=payload['run_evidence']['1']
    jobs=receipt['jobs'];artifacts=receipt['artifacts']
    sample_job=jobs['jobs'][0];sample_artifact=artifacts['artifacts'][0]
    jobs['jobs']=[dict(sample_job,id=i+1,name=n) for i,n in enumerate(sorted(m.CONTRACTS[name][1]))]
    artifacts['artifacts']=[dict(sample_artifact,id=i+1,name=n) for i,n in enumerate(sorted(m.CONTRACTS[name][2]))]
    jobs['total_count']=len(jobs['jobs']);artifacts['total_count']=len(artifacts['artifacts'])
    assert m.audit(payload,SHA)[name]['push']['state']=='PASS'
