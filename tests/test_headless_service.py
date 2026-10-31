"""Actual private loopback API and canonical disposable source checkout tests."""
import copy
import hashlib
import http.client
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time

import pytest
from meta_analyse import headless_service as service
from meta_analyse.grid_history_adapter import analyze_grid_history

ROOT=Path(__file__).parents[1]
TOKEN='a'*64
# Real owner bootstrap supplied by the coordinated Unified source checkout.
UNIFIED=Path(os.environ.get('UNIFIED_SOURCE_ROOT',ROOT.parent/'unified-system'))


def owned_argv(root):
    bootstrap=UNIFIED/'unified_system/owned_python.py'
    assert bootstrap.is_file(), 'Exact Unified bootstrap checkout required (UNIFIED_SOURCE_ROOT)'
    return [sys.executable,'-I','-S','-B',str(bootstrap),'--source-root',str(root),
            '--module','meta_analyse.headless_service','--','--execute','--port','0']


@pytest.fixture
def capsule(tmp_path):
    root=tmp_path/'capsule';package=root/'src/meta_analyse';package.mkdir(parents=True)
    cache=tmp_path/'private-cache';cache.mkdir(mode=0o700)
    for name in ('__init__.py','headless_service.py','core.py','grid_history_adapter.py'):
        shutil.copyfile(ROOT/'src/meta_analyse'/name,package/name)
    def git(*args):return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.DEVNULL).decode().strip()
    git('init');git('config','core.autocrlf','false');git('config','core.attributesFile',os.devnull)
    git('config','core.hooksPath',os.devnull);git('config','core.fsmonitor','false')
    git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','actual source fixture')
    exe=Path(shutil.which('git')).resolve()
    env=dict(os.environ,PYTHONPATH=str(root/'src'),PYTHONDONTWRITEBYTECODE='1',
             UNIFIED_MODULE_ID='meta_analyse',UNIFIED_MODULE_VERSION='0.1.0',
             UNIFIED_RELEASE_ID='release-test',UNIFIED_INSTANCE_TOKEN=TOKEN,
             UNIFIED_SOURCE_COMMIT=git('rev-parse','HEAD'),UNIFIED_PRIVATE_CACHE_ROOT=str(cache),
             UNIFIED_GIT_EXECUTABLE=str(exe),
             UNIFIED_GIT_SHA256=hashlib.sha256(exe.read_bytes()).hexdigest())
    return root,env,git


def launch(capsule):
    root,env,_=capsule
    process=subprocess.Popen(owned_argv(root),cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    lines=queue.Queue();reader=threading.Thread(target=lambda:lines.put(process.stdout.readline()),daemon=True);reader.start()
    try:
        line=lines.get(timeout=12)
        if not line:raise AssertionError('Service failed startup: '+process.stderr.read(1000))
        port=json.loads(line)['port']
        return process,port
    except BaseException:
        process.terminate();process.communicate(timeout=5);raise


@pytest.fixture
def running(capsule):
    process,port=launch(capsule)
    yield process,port,capsule
    process.terminate();process.communicate(timeout=5)
    assert process.returncode==0


def request(port,method='GET',path='/internal/v2/module/health',body=None,headers=None):
    con=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
    try:
        con.request(method,path,body=body,headers=headers if headers is not None else {'Authorization':'Bearer '+TOKEN})
        r=con.getresponse();return r.status,json.loads(r.read())
    finally:con.close()


def test_default_profile_prepares_without_owner_environment_or_listener(tmp_path):
    env={k:v for k,v in os.environ.items() if not k.startswith('UNIFIED_')}
    result=subprocess.run([sys.executable,'-B','-m','meta_analyse.headless_service'],env=dict(env,PYTHONPATH=str(ROOT/'src')),capture_output=True,text=True,timeout=5)
    assert result.returncode==0
    assert json.loads(result.stdout)=={'module_id':'meta_analyse','mode':'PREPARE_ONLY','listening':False,'execution_authority':False,'trading_authorized':False}


def test_health_matches_actual_root_driver_five_field_contract(running):
    _,port,_=running
    status,body=request(port)
    assert status==200
    assert body==dict(module_id='meta_analyse',version='0.1.0',release_id='release-test',instance_token=TOKEN,ready=True)


def test_actual_adapter_and_causal_prefix_remain_unqualified(running):
    _,port,_=running
    payload=json.loads((ROOT/'tests/fixtures/grid_history/synthetic-v11.json').read_bytes())
    headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'}
    for decision in (59999,120000,180000):
        status,out=request(port,'POST','/internal/v1/history/analyze',json.dumps(dict(payload=payload,decision_ms=decision)),headers)
        assert status==200 and out==analyze_grid_history(payload,decision_ms=decision)
        assert all(out[k] is False for k in ('execution_authority','trading_authorized','training_authorized'))
        assert out['source_authenticity']=='NOT_EVALUATED'
    forged=copy.deepcopy(payload);forged['rows'][0]['close']=999
    assert request(port,'POST','/internal/v1/history/analyze',json.dumps(dict(payload=forged,decision_ms=180000)),headers)[0]==422


@pytest.mark.parametrize('headers',[
    {},{'Authorization':'Bearer '+'b'*64},{'Authorization':'bearer '+TOKEN},
    {'Authorization':'Bearer '+TOKEN,'Origin':'http://127.0.0.1'},
    {'Authorization':'Bearer '+TOKEN,'Host':'office.invalid'},
])
def test_auth_and_browser_or_host_forgery_rejected(running,headers):
    assert request(running[1],headers=headers)[0] in (401,403)


def test_routes_methods_strict_json_and_bounds(running):
    port=running[1];headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'}
    assert request(port,'PUT')[0]==405
    assert request(port,path='/internal/v2/module/health?x=1')[0]==404
    for raw in ('{"payload":{},"payload":{},"decision_ms":1}', '{"payload":{},"decision_ms":NaN}', '{"payload":{},"decision_ms":1e309}', '[]'):
        assert request(port,'POST','/internal/v1/history/analyze',raw,headers)[0]==422
    assert request(port,'POST','/internal/v1/history/analyze','{}',dict(headers,**{'Content-Length':str(service.MAX_BODY+1)}))[0]==413
    con=socket.create_connection(('127.0.0.1',port),timeout=3)
    try:
        con.sendall((f'GET /internal/v2/module/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {TOKEN}\r\nAuthorization: Bearer {TOKEN}\r\n\r\n').encode())
        assert b'401' in con.recv(1024).split(b'\r\n',1)[0]
    finally:con.close()


@pytest.mark.parametrize('stage',('headers','body'))
def test_trickled_headers_hit_absolute_deadline_and_leave_service_healthy(running,stage):
    port=running[1];con=socket.create_connection(('127.0.0.1',port),timeout=5)
    started=time.monotonic()
    try:
        if stage=='headers':con.sendall(b'GET /internal/v2/module/health HTTP/1.1\r\nX-Trickle: ')
        else:con.sendall((f'POST /internal/v1/history/analyze HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n{{').encode())
        for _ in range(30):
            try:con.sendall(b'a')
            except OSError:break
            time.sleep(.15)
        assert con.recv(1024)==b''
    except (ConnectionResetError,BrokenPipeError):pass
    finally:con.close()
    assert time.monotonic()-started<5
    assert request(port)[0]==200


def test_dirty_source_or_wrong_pin_fails_before_bind(capsule):
    root,env,_=capsule
    for mutation in ('dirty','wrong-pin','untracked','filter'):
        changed=dict(env)
        if mutation=='dirty':(root/'src/meta_analyse/core.py').write_text('# changed\n')
        if mutation=='wrong-pin':changed['UNIFIED_SOURCE_COMMIT']='b'*40
        if mutation=='untracked':(root/'src/meta_analyse/shadow.py').write_text('')
        if mutation=='filter':subprocess.run(['git','-C',str(root),'config','filter.bad.clean','echo unsafe'],check=True)
        result=subprocess.run(owned_argv(root),cwd=root,env=changed,capture_output=True,text=True,timeout=10)
        assert result.returncode==2 and not result.stdout and 'BLOCKED' in result.stderr
        if mutation=='dirty':shutil.copyfile(ROOT/'src/meta_analyse/core.py',root/'src/meta_analyse/core.py')
        if mutation=='untracked':(root/'src/meta_analyse/shadow.py').unlink()


def test_runtime_source_change_never_reports_ready(running):
    _,port,(root,_,_)=running
    with (root/'src/meta_analyse/core.py').open('a') as stream:stream.write('\n# changed\n')
    assert request(port)[0]==503


def test_bounded_concurrency_recovers_after_slow_body_connections(running):
    port=running[1];connections=[]
    try:
        for _ in range(4):
            con=socket.create_connection(('127.0.0.1',port),timeout=4)
            con.sendall((f'POST /internal/v1/history/analyze HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{{').encode())
            connections.append(con)
        time.sleep(.15)
        con=socket.create_connection(('127.0.0.1',port),timeout=4)
        try:
            con.sendall(b'GET / HTTP/1.0\r\n\r\n')
            assert b'503' in con.recv(1024).split(b'\r\n',1)[0]
        finally:con.close()
    finally:
        for con in connections:con.close()
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        try:
            if request(port)[0]==200:break
        except (OSError,ValueError,http.client.HTTPException):pass
        time.sleep(.05)
    else:pytest.fail('bounded slots did not recover')


def test_source_rejects_index_staging_overrides_and_noncanonical_raw_bytes(capsule):
    root,env,git=capsule
    identity=service.Identity.from_environment(env)
    verifier=service.SourceVerifier(root,identity)
    verifier.verify()
    file=root/'src/meta_analyse/core.py'
    original=file.read_bytes();file.write_bytes(original.replace(b'\n',b'\r\n'))
    with pytest.raises(ValueError):verifier.verify()
    file.write_bytes(original)
    (root/'added.txt').write_text('staged');git('add','added.txt')
    with pytest.raises(ValueError):verifier.verify()


def test_execute_without_owned_environment_denies_before_listener(tmp_path):
    env={k:v for k,v in os.environ.items() if not k.startswith('UNIFIED_')}
    result=subprocess.run([sys.executable,'-B','-m','meta_analyse.headless_service','--execute'],env=dict(env,PYTHONPATH=str(ROOT/'src')),capture_output=True,text=True,timeout=5)
    assert result.returncode==2 and not result.stdout and 'BLOCKED' in result.stderr


def test_partial_clone_lazy_fetch_configuration_is_rejected(capsule):
    root,env,git=capsule
    identity=service.Identity.from_environment(env)
    service.SourceVerifier(root,identity).verify()
    git('config','extensions.partialClone','origin')
    git('config','remote.origin.promisor','true')
    with pytest.raises(ValueError):service.SourceVerifier(root,identity).verify()


def test_external_poisoned_timestamp_bytecode_is_not_consumed(capsule,tmp_path):
    import importlib.util
    import py_compile
    root,env,_=capsule
    actual=root/'src/meta_analyse/grid_history_adapter.py'
    fake=tmp_path/'poison.py'
    evil=b"def analyze_grid_history(*args,**kwargs): return {'execution_authority': True, 'trading_authorized': True, 'training_authorized': True}\n"
    fake.write_bytes(evil+b'#'*(actual.stat().st_size-len(evil)))
    os.utime(fake,ns=(actual.stat().st_atime_ns,actual.stat().st_mtime_ns))
    cache=tmp_path/'external-cache';cache.mkdir()
    previous=sys.pycache_prefix
    try:
        sys.pycache_prefix=str(cache)
        target=importlib.util.cache_from_source(str(actual))
    finally:sys.pycache_prefix=previous
    py_compile.compile(str(fake),cfile=target,dfile=str(actual),doraise=True)
    changed=(root,dict(env,PYTHONPYCACHEPREFIX=str(cache)),capsule[2])
    process,port=launch(changed)
    try:
        assert request(port)[0]==200
        status,body=request(port,'POST','/internal/v1/history/analyze','{"payload":{},"decision_ms":1}',{'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
        assert status==422 and body['execution_authority'] is False
    finally:process.terminate();process.communicate(timeout=5)


def test_plain_module_execution_is_not_an_owned_cache_isolation_profile(capsule):
    root,env,_=capsule
    result=subprocess.run([sys.executable,'-B','-m','meta_analyse.headless_service','--execute','--port','0'],cwd=root,env=env,capture_output=True,text=True,timeout=5)
    assert result.returncode==2 and not result.stdout and 'BLOCKED' in result.stderr


@pytest.mark.parametrize('key,value',[
    ('execution_authority',True),('trading_authorized',True),('training_authorized',True),
    ('execution_authority',0),('schema','unrelated.schema'),
    ('source_authenticity','OWNER_POLICY_ADMITTED'),('quality_status','COMPLETE'),
])
def test_real_http_rejects_clean_pinned_backend_contract_drift(capsule,key,value):
    root,env,git=capsule
    adapter=root/'src/meta_analyse/grid_history_adapter.py'
    # Adversarial future producer regression, committed as an exact test capsule.
    # Actual analysis still runs; its forged output must never be repaired/passed.
    with adapter.open('a') as stream:
        stream.write('\n_original_analysis=analyze_grid_history\ndef analyze_grid_history(*args,**kwargs):\n    out=_original_analysis(*args,**kwargs)\n    out['+repr(key)+']='+repr(value)+'\n    return out\n')
    git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','adversarial backend drift')
    changed=(root,dict(env,UNIFIED_SOURCE_COMMIT=git('rev-parse','HEAD')),git)
    process,port=launch(changed)
    try:
        payload=json.loads((ROOT/'tests/fixtures/grid_history/synthetic-v11.json').read_bytes())
        status,out=request(port,'POST','/internal/v1/history/analyze',json.dumps(dict(payload=payload,decision_ms=180000)),{'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
        assert status==422 and out['error']=='REQUEST_UNAVAILABLE'
        assert 'candles' not in out and 'dataset_id' not in out
    finally:process.terminate();process.communicate(timeout=5)


def test_git_http_alternates_metadata_is_rejected_before_object_reads(capsule):
    root,env,_=capsule
    identity=service.Identity.from_environment(env)
    service.SourceVerifier(root,identity).verify()
    # No objects are missing and no network is called; the metadata itself is
    # forbidden even before Git could use it as a remote object fallback.
    (root/'.git/objects/info/http-alternates').write_text('https://example.invalid/never-contacted\n')
    with pytest.raises(ValueError):service.SourceVerifier(root,identity).verify()
