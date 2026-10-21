import copy
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'commissioning'))
import host_identity as h

def target():
    return dict(collector_elevated=True,identity=dict(hostname='ADMINIT-JQ1IQSV', username=r'ADMINIT-JQ1IQSV\Administrator', sid='S-test', machine_guid='new-install', install_id='new', hardware_uuid='hardware'),
        os=dict(system='Windows', edition='Professional', build=26100),
        grid=dict(findings=[], errors=[], coverage_complete=True),
        metascalp=[dict(path=h.TARGET_EXE, sha256=h.TARGET_EXE_SHA256, signature='Valid', publisher='CN=Grigoryan Construct LLC', file_version='1.0.291')],
        api_listeners=[dict(port=17845, address='127.0.0.1', exe_sha256=h.TARGET_EXE_SHA256, pid=22676, process_started='2026-10-20', exe_path=h.TARGET_EXE)])

def policy(f):
    return h.make_policy(f,salt='a'*64,candidate_sha='1'*40,manifest_sha256='2'*64,dbname='meta_commission_case',user='meta_commission_case',port=55480,data_directory='C:/new/pgdata',metascalp=dict(path=h.TARGET_EXE,sha256=h.TARGET_EXE_SHA256),operator_approved=True,confirm_no_grid=True,now=1000)

def test_adminit_enrolls_and_ls5_does_not():
    f=target(); p=policy(f)
    assert h.validate_policy(f,p,expected_name='ADMINIT-JQ1IQSV',candidate_sha='1'*40,manifest_sha256='2'*64,now=1001)=='ADMINIT-JQ1IQSV'
    f['identity'].update(hostname='LS5',username=r'LS5\LS-5')
    with pytest.raises(ValueError): policy(f)

@pytest.mark.parametrize('field,value',[('port',5432),('dbname','postgres'),('user','postgres')])
def test_target_policy_rejects_existing_cluster(field,value):
    f=target(); p=policy(f); p['database'][field]=value
    with pytest.raises(ValueError): h.validate_policy(f,p,expected_name='ADMINIT-JQ1IQSV',candidate_sha='1'*40,manifest_sha256='2'*64,now=1001)

@pytest.mark.parametrize('fault',['hash','publisher','port','pid','path'])
def test_exact_terminal_identity_fails_closed(fault):
    f=target()
    if fault=='hash': f['metascalp'][0]['sha256']='b'*64
    if fault=='publisher': f['metascalp'][0]['publisher']='Other publisher'
    if fault=='port': f['api_listeners'][0]['port']=17846
    if fault=='pid': f['api_listeners'][0].pop('pid')
    if fault=='path': f['api_listeners'][0]['exe_path']='C:/Other.exe'
    with pytest.raises(ValueError): h.validate_metascalp(f,h.TARGET_EXE)

def test_process_restart_invalidates_enrollment():
    f=target(); p=policy(f); f['api_listeners'][0]['pid']=22677
    with pytest.raises(ValueError): h.validate_policy(f,p,expected_name='ADMINIT-JQ1IQSV',candidate_sha='1'*40,manifest_sha256='2'*64,now=1001)

def test_http_sys_queue_ownership_requires_exact_single_process():
    text='Request queue name: unnamed\n    Number of active processes attached: 1\n    Processes:\n        ID: 22676, image: C:\\MetaScalp.exe\n    URL groups:\n        Registered URLs:\n            HTTP://127.0.0.1:17845:127.0.0.1/\n'
    assert h.http_sys_owner(text,17845)==22676
    for invalid in (text.replace('attached: 1','attached: 2'),text.replace('127.0.0.1:17845','*:17845'),text.replace('17845','17846')):
        with pytest.raises(ValueError):h.http_sys_owner(invalid,17845)

def test_pg186_is_not_pg181():
    import preflight
    class C:
        def execute(self,sql): return self
        def fetchone(self): return ('180006',)
    with pytest.raises(ValueError,match='18.1'):preflight.verify_database_role(C(),policy(target()))

@pytest.mark.parametrize('existing',[True,False])
def test_new_schema_check_and_ddl_share_transaction_and_lock(monkeypatch,existing):
    import importlib.util
    spec=importlib.util.spec_from_file_location('schema_setup',Path(h.__file__).with_name('initialize-private-schema.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    calls=[]
    class Connection:
        def __enter__(self):calls.append('begin');return self
        def __exit__(self,*args):calls.append('rollback' if args[0] else 'commit')
        def execute(self,sql,*args):calls.append(sql);return self
        def fetchone(self):return (existing,)
    monkeypatch.setattr(module.psycopg,'connect',lambda **kwargs:Connection())
    monkeypatch.setattr(module,'verify_database_role',lambda *args:calls.append('verify_role'))
    if existing:
        with pytest.raises(ValueError):module.initialize_new_schema({}, {})
        assert calls[-1]=='rollback'
    else:
        module.initialize_new_schema({}, {})
        assert calls[-1]=='commit'
        assert any('CREATE SCHEMA' in s for s in calls)
    assert calls[2].startswith('SELECT pg_advisory_xact_lock')
    assert 'pg_namespace' in calls[3] and 'pg_proc' in calls[3]
    if existing: assert not any('CREATE SCHEMA' in s for s in calls)
