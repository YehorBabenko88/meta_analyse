"""Synthetic harness boundaries; physical stages never execute here."""
import json
import os
import shutil
import subprocess
from pathlib import Path
import sys

import pytest
from scripts import local_smoke as smoke

SHA='a'*40;TREE='b'*40;SECRET='PRIVATE_TOKEN_HOST_PATH'
ROOT=str(Path.cwd().resolve());PYTHON=str(Path(sys.executable).resolve())
GIT=str((Path.cwd()/'synthetic-git.exe').resolve())
GOOD=dict(schema=1,isolated=True,no_site=True,bytecode_disabled=True,python312=True,bits64=True,imports_ok=True)

class Runner:
    def __init__(self,fault=None):self.calls=[];self.fault=fault
    def __call__(self,argv,**kw):
        self.calls.append(argv)
        if self.fault=='timeout':raise subprocess.TimeoutExpired('PRIVATE',1,output=SECRET.encode())
        if self.fault=='exception':raise OSError(SECRET)
        if argv[0]==GIT:
            output=SHA if argv[-1]=='HEAD' else TREE if argv[-1]=='HEAD^{tree}' else ''
            if self.fault=='wrong_sha' and argv[-1]=='HEAD':output='f'*40
            if self.fault=='dirty' and 'status' in argv:output=SECRET
            return subprocess.CompletedProcess(argv,1 if self.fault=='git_exit' else 0,output.encode())
        data=dict(GOOD)
        if self.fault in data:data[self.fault]=False
        if self.fault=='bool_schema':data['schema']=True
        if self.fault=='extra':data[SECRET]=SECRET
        raw=json.dumps(data).encode()
        if self.fault=='malformed':raw=SECRET.encode()
        if self.fault=='duplicate':raw=b'{"schema":1,"schema":1}'
        if self.fault=='oversize':raw=b'x'*4097
        return subprocess.CompletedProcess(argv,7 if self.fault=='child_exit' else 0,raw)

def execute(runner=None,**kw):
    args=dict(stage='S0',expected_sha=SHA,expected_tree=TREE,repo=ROOT,
              python=PYTHON,git=GIT,operator_approved=False)
    args.update(kw)
    return smoke.run_smoke(**args,runner=runner or Runner())

def test_s0_is_once_isolated_and_never_authorizes_next_stage():
    runner=Runner();r=execute(runner,operator_approved=True)
    assert r['outcome']=='PASS_SMOKE_ONLY' and r['exit_code']==0 and r['child_exit_code']==0
    assert r['authorization']=='NONE' and r['g0_status']=='FAIL_CLOSED' and r['next_stage']=='BLOCKED'
    child=[c for c in runner.calls if c[0]==PYTHON]
    assert len(child)==1 and child[0][1:4]==['-I','-S','-B']
    assert r['source_sha']==SHA and r['source_tree']==TREE and 0<=r['elapsed_ms']<=15000

@pytest.mark.parametrize('stage',['S1','S2','S3','S4','UNKNOWN'])
def test_unimplemented_stage_never_runs_any_command(stage):
    runner=Runner();r=execute(runner,stage=stage,operator_approved=True)
    assert r['outcome']=='BLOCKED' and r['exit_code']==2 and runner.calls==[]

def test_without_explicit_operator_decision_no_command_runs():
    runner=Runner();assert execute(runner)['outcome']=='BLOCKED' and runner.calls==[]

@pytest.mark.parametrize('fault',['wrong_sha','dirty','git_exit','timeout','exception','child_exit',
    'isolated','no_site','bytecode_disabled','python312','bits64','imports_ok',
    'bool_schema','extra','malformed','duplicate','oversize'])
def test_bad_source_runtime_or_child_output_fails_without_retry_or_leak(fault):
    runner=Runner(fault);r=execute(runner,operator_approved=True)
    assert r['outcome'] in ('FAIL','BLOCKED') and r['exit_code']!=0
    assert len([c for c in runner.calls if c[0]==PYTHON])<=1
    assert SECRET not in json.dumps(r) and len(json.dumps(r).encode())<=2048

@pytest.mark.parametrize('field,value',[('expected_sha',SECRET),('expected_tree',None),
    ('python','relative.exe'),('git','git'),('operator_approved',1)])
def test_malformed_inputs_block_before_source_or_child(field,value):
    runner=Runner();r=execute(runner,**{field:value})
    assert r['outcome']=='BLOCKED' and runner.calls==[] and SECRET not in json.dumps(r)

def test_real_synthetic_child_imports_only_under_isolation():
    # This is a local/hosted interpreter smoke, not physical ADMINIT acceptance.
    result=subprocess.run([PYTHON,'-I','-S','-B','-c',smoke.CHILD],
                          stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=8)
    assert result.returncode==0 and json.loads(result.stdout)==GOOD

def test_source_change_after_child_cannot_leave_pass():
    class Changing(Runner):
        def __call__(self,argv,**kw):
            result=super().__call__(argv,**kw)
            if argv[-1]=='HEAD' and len([c for c in self.calls if c[-1]=='HEAD'])==2:
                result.stdout=b'f'*40
            return result
    r=execute(Changing(),operator_approved=True)
    assert r['outcome']=='FAIL' and r['source_bound'] is False and r['reason']=='SOURCE_CHANGED'

def test_malformed_cli_is_private(capsys):
    assert smoke.main(['--private-bad-argument',SECRET])==2
    capture=capsys.readouterr()
    assert SECRET not in capture.out+capture.err
    assert json.loads(capture.out)['outcome']=='BLOCKED'

def test_postcheck_exception_never_claims_bound_source():
    class PostFailure(Runner):
        def __call__(self,argv,**kw):
            if argv[0]==GIT and any(c[0]==PYTHON for c in self.calls):raise OSError(SECRET)
            return super().__call__(argv,**kw)
    r=execute(PostFailure(),operator_approved=True)
    assert r['outcome']=='FAIL' and r['source_bound'] is False

def test_oversized_child_output_retains_observed_exit_code():
    r=execute(Runner('oversize'),operator_approved=True)
    assert r['outcome']=='FAIL' and r['child_exit_code']==0

def test_real_synthetic_checkout_and_child(monkeypatch,tmp_path):
    git=shutil.which('git');assert git
    for key in list(os.environ):
        if key.startswith('GIT_'):monkeypatch.delenv(key)
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM','1')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL',os.devnull)
    def call(*args):
        return subprocess.check_output([git,'-c','core.hooksPath='+os.devnull,
            '-c','commit.gpgsign=false','-C',str(tmp_path),*args],stderr=subprocess.DEVNULL).decode().strip()
    call('init','-q');call('config','user.name','Synthetic');call('config','user.email','synthetic@example.invalid')
    (tmp_path/'source.txt').write_text('synthetic only')
    call('add','source.txt');call('commit','-qm','synthetic')
    r=smoke.run_smoke(stage='S0',expected_sha=call('rev-parse','HEAD'),
        expected_tree=call('rev-parse','HEAD^{tree}'),repo=str(tmp_path),python=PYTHON,
        git=str(Path(git).resolve()),operator_approved=True)
    assert r['outcome']=='PASS_SMOKE_ONLY' and r['source_bound'] is True and r['attempts']==1
