"""Offline evidence gates never authorize or execute commissioning stages."""
import sys
from pathlib import Path
import copy
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'commissioning'))


def module():
    import stage_acceptance
    return stage_acceptance


def sample(stage):
    m=module();sha='a'*40;tree='b'*40
    evidence=dict(source=dict(sha=sha,tree=tree),checks={key:'PASS' for key in m.CHECKS[stage]},
                  metrics=dict(cpu_peak_percent=10,memory_delta_mb=10,free_disk_mb=20000,
                               queue_depth=0,active_writes=0,ui_age_seconds=1,elapsed_seconds=m.DURATIONS[stage],
                               unresolved_processes=0))
    previous=None if stage=='G0' else dict(stage='G'+str(int(stage[1])-1),status='PASS',sha=sha,tree=tree)
    return sha,tree,evidence,previous


@pytest.mark.parametrize('stage',['G0','G1','G2','G3','G4','G5'])
def test_stage_evidence_never_grants_authorization_or_advances(stage):
    sha,tree,e,previous=sample(stage)
    r=module().evaluate_stage(stage,sha,tree,e,operator_approved=True,previous=previous)
    assert r['status']=='PASS' and r['authorization']=='NONE' and r['next_stage_started'] is False
    assert r['scope']=='SUBMITTED_EVIDENCE_ONLY'


@pytest.mark.parametrize('fault',['sha','tree','missing_check','failed_check','unresolved','cpu','ram','disk','nan','bool_metric'])
def test_g0_malformed_refusal_or_budget_cannot_pass(fault):
    sha,tree,e,previous=sample('G0')
    if fault in ('sha','tree'):e['source'][fault]='c'*40
    if fault=='missing_check':e['checks'].pop('ci')
    if fault=='failed_check':e['checks']['ci']='FAIL'
    if fault=='unresolved':e['metrics']['unresolved_processes']=7
    if fault=='cpu':e['metrics']['cpu_peak_percent']=95
    if fault=='ram':e['metrics']['memory_delta_mb']=2048
    if fault=='disk':e['metrics']['free_disk_mb']=100
    if fault=='nan':e['metrics']['elapsed_seconds']=float('nan')
    if fault=='bool_metric':e['metrics']['unresolved_processes']=False
    r=module().evaluate_stage('G0',sha,tree,e,operator_approved=True,previous=previous)
    assert r['status'] in ('FAIL','BLOCKED') and r['authorization']=='NONE'


@pytest.mark.parametrize('fault',['approval','previous','previous_sha','duration','queue','write_drain','ui_age','checkpoint'])
def test_runtime_stages_require_independent_gate_and_stop_conditions(fault):
    sha,tree,e,previous=sample('G3');approved=True
    if fault=='approval':approved=False
    if fault=='previous':previous=None
    if fault=='previous_sha':previous['sha']='c'*40
    if fault=='duration':e['metrics']['elapsed_seconds']=1799
    if fault=='queue':e['metrics']['queue_depth']=1025
    if fault=='write_drain':e['metrics']['active_writes']=1
    if fault=='ui_age':e['metrics']['ui_age_seconds']=10
    if fault=='checkpoint':e['checks']['checkpoint']='BLOCKED'
    r=module().evaluate_stage('G3',sha,tree,e,operator_approved=approved,previous=previous)
    assert r['status']!='PASS' and r['authorization']=='NONE'


def test_stage_boundary_discards_private_and_malformed_inputs():
    r=module().evaluate_stage('PRIVATE_HOST','secret',None,dict(raw='PRIVATE_DSN'))
    assert r['status']=='BLOCKED' and 'PRIVATE' not in repr(r)

def test_stage_source_checks_survive_optimized_python():
    import subprocess,json
    code="import sys,json;sys.path.insert(0,sys.argv[1]);import stage_acceptance as m;"+"e=dict(source=dict(sha='c'*40,tree='b'*40),checks={k:'PASS' for k in m.CHECKS['G0']},metrics=dict(cpu_peak_percent=1,memory_delta_mb=1,free_disk_mb=20000,queue_depth=0,active_writes=0,ui_age_seconds=0,elapsed_seconds=0,unresolved_processes=0));print(json.dumps(m.evaluate_stage('G0','a'*40,'b'*40,e)))"
    data=subprocess.check_output([sys.executable,'-O','-B','-c',code,str(Path(__file__).resolve().parents[1]/'commissioning')],text=True)
    assert json.loads(data)['status']=='BLOCKED'
