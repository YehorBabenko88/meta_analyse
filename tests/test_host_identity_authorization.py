import copy, json, sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'commissioning'))
import host_identity as h

@pytest.fixture
def facts():
    return dict(collector_elevated=True,identity=dict(hostname='ADMINIT-JQ1IQSV',username='ADMINIT-JQ1IQSV\\Administrator',sid='S-1-test',machine_guid='installation-a',install_id='2026-install',hardware_uuid='hardware-a'),
        os=dict(system='Windows',edition='Professional',build=26300),
        grid=dict(findings=[],errors=[],coverage_complete=True),credential_names=[],production_dsn_names=[],
        postgres_listeners=[dict(port=55480,address='127.0.0.1',data_directory='C:/private/commission/pgdata')],
        metascalp=[dict(path=h.TARGET_EXE,signature='Valid',sha256=h.TARGET_EXE_SHA256,file_version='1.0.291',publisher='CN=Grigoryan Construct LLC')],
        api_listeners=[dict(port=17845,address='127.0.0.1',exe_sha256=h.TARGET_EXE_SHA256,pid=22676,process_started='test',exe_path=h.TARGET_EXE)])

@pytest.fixture
def policy(facts):
    return h.make_policy(facts,salt='a'*64,candidate_sha='1'*40,manifest_sha256='2'*64,
        dbname='meta_commission_case',user='meta_commission_case',port=55480,
        data_directory='C:/private/commission/pgdata',metascalp=dict(path=h.TARGET_EXE,sha256=h.TARGET_EXE_SHA256),operator_approved=True,confirm_no_grid=True,now=1000)

def check(facts,policy):
    return h.validate_policy(facts,policy,expected_name='ADMINIT-JQ1IQSV',candidate_sha='1'*40,manifest_sha256='2'*64,now=1001)

def test_specific_verified_host_can_pass(facts,policy): assert check(facts,policy)=='ADMINIT-JQ1IQSV'

@pytest.mark.parametrize('field',['machine_guid','hardware_uuid','install_id','sid'])
def test_same_hostname_other_identity_fails(facts,policy,field):
    facts['identity'][field]='different'
    with pytest.raises(ValueError): check(facts,policy)

@pytest.mark.parametrize('section,value',[('findings',['Grid service']),('errors',['AccessDenied']),('coverage_complete',False)])
def test_grid_or_incomplete_inventory_fails(facts,policy,section,value):
    facts['grid'][section]=value
    with pytest.raises(ValueError): check(facts,policy)

@pytest.mark.parametrize('key',['credential_names','production_dsn_names'])
def test_credentials_or_production_environment_fail(facts,policy,key):
    facts[key]=['BYBIT_API_KEY' if key=='credential_names' else 'GRID_PRODUCTION_DSN']
    with pytest.raises(ValueError): check(facts,policy)

@pytest.mark.parametrize('change',[dict(operator_approved=False),dict(confirm_no_grid=False),dict(expires_at=999),dict(issued_at=1002)])
def test_absent_approval_and_stale_authorization_fail(facts,policy,change):
    policy.update(change)
    with pytest.raises(ValueError): check(facts,policy)

@pytest.mark.parametrize('dsn',[
 'host=198.51.100.1 port=55480 dbname=meta_commission_case user=meta_commission_case',
 'host=127.0.0.1 port=55480 dbname=postgres user=meta_commission_case',
 'host=127.0.0.1 port=55480 dbname=meta_commission_case user=postgres',
 'host=127.0.0.1 port=55432 dbname=meta_commission_case user=meta_commission_case'])
def test_remote_wrong_database_role_or_port_fail(facts,policy,dsn):
    with pytest.raises(ValueError): h.validate_bound_database(dsn,policy,{})

def test_hidden_libpq_override_fails(policy):
    with pytest.raises(ValueError):h.validate_bound_database('host=127.0.0.1 port=55480 dbname=meta_commission_case user=meta_commission_case',policy,{'PGOPTIONS':'anything'})

def test_wrong_sha_fails(facts,policy):
    with pytest.raises(ValueError):h.validate_policy(facts,policy,expected_name='ADMINIT-JQ1IQSV',candidate_sha='3'*40,manifest_sha256='2'*64,now=1001)

def test_unverified_postgres_metascalp_or_tls_fail():
    for key in ['postgres','metascalp','tls']:
        evidence=dict(postgres='PASS',metascalp='PASS',tls='PASS');evidence[key]='NOT_RUN'
        with pytest.raises(ValueError):h.require_preflight(evidence)

def test_public_report_contains_no_raw_identifiers(facts):
    result=json.dumps(h.public_report(facts,'a'*64))
    for key in ['sid','machine_guid','install_id','hardware_uuid']:
        assert facts['identity'][key] not in result

def test_wildcard_or_wrong_cluster_listener_fails(facts,policy):
    facts['postgres_listeners'][0]['address']='0.0.0.0'
    with pytest.raises(ValueError):h.validate_cluster_listener(facts,policy)

def test_manifest_empty_or_wrong_sha_never_passes(tmp_path):
    import hashlib
    import preflight
    manifest=tmp_path/'CANDIDATE.json'
    manifest.write_text(json.dumps(dict(candidate_sha='1'*40,source_root='source',files=[])))
    (tmp_path/'source').mkdir()
    digest=hashlib.sha256(manifest.read_bytes()).hexdigest()
    with pytest.raises(ValueError):preflight.verify_manifest(manifest,'1'*40,digest)
    with pytest.raises(ValueError):preflight.verify_manifest(manifest,'3'*40,digest)

@pytest.mark.parametrize('condition',['missing','invalid-signature','no-api'])
def test_metascalp_missing_untrusted_or_api_absent_is_blocking(facts,condition):
    facts['metascalp']=[] if condition=='missing' else [dict(path=h.TARGET_EXE,signature='Valid' if condition=='no-api' else 'NotSigned',sha256=h.TARGET_EXE_SHA256)]
    facts['api_listening_ports']=[]
    facts['api_listeners']=[]
    with pytest.raises(ValueError):h.validate_metascalp(facts,h.TARGET_EXE)

def test_cross_machine_private_authorization_decryption_fails(monkeypatch,tmp_path):
    monkeypatch.setattr(h,'dpapi',lambda data,**kw: (_ for _ in ()).throw(ValueError('not this user/machine')))
    p=tmp_path/'enrollment.dpapi';p.write_bytes(b'YWJj')
    with pytest.raises(ValueError):h.load_private(p)

def test_windows_dpapi_tamper_or_other_platform_fails_closed():
    import platform
    if platform.system()=='Windows':
        protected=h.dpapi(b'nonsecret unit-test policy')
        assert h.dpapi(protected,decrypt=True)==b'nonsecret unit-test policy'
        with pytest.raises(ValueError):h.dpapi(protected[:-8]+b'bad-data',decrypt=True)
    else:
        with pytest.raises(ValueError):h.dpapi(b'not-windows')

@pytest.mark.parametrize('field',['machine_guid','hardware_uuid','sid'])
def test_missing_identity_input_fails(facts,policy,field):
    facts['identity'][field]=None
    with pytest.raises(ValueError):check(facts,policy)

def test_modified_source_or_untrusted_manifest_digest_fails(tmp_path):
    import hashlib
    import preflight
    root=tmp_path/'source';root.mkdir()
    paths=['pyproject.toml','requirements.lock','commissioning/host_identity.py','commissioning/host-facts.ps1','commissioning/preflight.py','commissioning/run_readonly.py','src/meta_analyse/desktop.py']
    items=[]
    for name in paths:
        f=root/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('fixture')
        items.append(dict(path=name,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
    manifest=tmp_path/'CANDIDATE.json';manifest.write_text(json.dumps(dict(candidate_sha='1'*40,source_root='source',files=items)))
    digest=hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert preflight.verify_manifest(manifest,'1'*40,digest)==root
    with pytest.raises(ValueError):preflight.verify_manifest(manifest,'1'*40,'0'*64)
    (root/'src/meta_analyse/desktop.py').write_text('modified')
    with pytest.raises(ValueError):preflight.verify_manifest(manifest,'1'*40,digest)

def test_failed_tls_never_reaches_qt_or_runtime(monkeypatch):
    import ssl
    import run_readonly
    args=['launcher','--manifest','unused','--manifest-sha256','2'*64,'--expected-sha','1'*40,
          '--expected-computer','LS5','--enrollment','unused','--metascalp-exe','unused','--log-dir','unused','--operator-approved-readonly-run']
    monkeypatch.setattr(sys,'argv',args)
    async def fail(_):raise ssl.SSLCertVerificationError('fixture')
    monkeypatch.setattr(run_readonly,'inspect',fail)
    monkeypatch.setattr(run_readonly,'install_http_read_guard',lambda:pytest.fail('runtime must not begin'))
    with pytest.raises(ssl.SSLCertVerificationError):run_readonly.main()

def test_guard_cannot_authorize_install_from_different_checkout(monkeypatch,tmp_path):
    from types import SimpleNamespace
    import preflight
    args=SimpleNamespace(manifest='unused',expected_sha='1'*40,manifest_sha256='2'*64,enrollment='unused',expected_computer='LS5')
    monkeypatch.setattr(preflight,'verify_manifest',lambda *a:tmp_path/'another-packet')
    monkeypatch.setattr(h,'collect_facts',lambda:pytest.fail('wrong executing root must fail first'))
    with pytest.raises(ValueError,match='executing'):h.authorize(args)

@pytest.mark.asyncio
async def test_runtime_terminal_does_not_rescan_another_port(monkeypatch,facts):
    import run_readonly
    from meta_analyse.ports import MetaScalp
    monkeypatch.setattr(MetaScalp,'discover',MetaScalp.discover)
    monkeypatch.setattr(MetaScalp,'request',MetaScalp.request)
    monkeypatch.setattr(h,'collect_facts',lambda:facts)
    run_readonly.bind_terminal_endpoint(dict(metascalp_exe_sha256=h.TARGET_EXE_SHA256,metascalp_api_port=17845,metascalp_pid=22676,metascalp_process_started='test'),h.TARGET_EXE)
    client=MetaScalp()
    try:
        assert await client.discover()=='http://127.0.0.1:17845'
        facts['api_listeners'][0]['port']=17846
        with pytest.raises(ConnectionError):await client.discover()
    finally:await client.close()

def test_ls7_or_another_operator_cannot_enroll(facts):
    facts['identity']['hostname']='LS7'
    facts['identity']['username']='LS7\\LS-7'
    with pytest.raises(ValueError):h.make_policy(facts,salt='a'*64,candidate_sha='1'*40,manifest_sha256='2'*64,
        dbname='meta_commission_case',user='meta_commission_case',port=55480,data_directory='C:/private/pgdata',
        metascalp=dict(path=h.TARGET_EXE,sha256=h.TARGET_EXE_SHA256),operator_approved=True,confirm_no_grid=True)

@pytest.mark.parametrize('fault',['superuser','createdb','createrole','replication','bypassrls','membership','public-connect','wrong-owner','wrong-version'])
def test_excess_database_privileges_and_cross_database_connect_are_rejected(policy,fault):
    import preflight
    class Row:
        def __init__(self,value):self.value=value
        def fetchone(self):return self.value
    class Connection:
        def execute(self,sql):
            if sql.startswith('SHOW'):return Row(('170006' if fault=='wrong-version' else '180006',))
            if 'pg_get_userbyid' in sql:
                return Row(('meta_commission_case','meta_commission_case','meta_commission_case','postgres' if fault=='wrong-owner' else 'meta_commission_case'))
            if 'rolsuper' in sql:
                indexes={'superuser':0,'createrole':1,'createdb':2,'replication':3,'bypassrls':4}
                values=[False]*5+[True]
                if fault in indexes:values[indexes[fault]]=True
                return Row(tuple(values))
            if 'pg_auth_members' in sql:return Row((fault=='membership',))
            if 'has_database_privilege' in sql:return Row((1 if fault=='public-connect' else 0,))
            pytest.fail('unexpected SQL')
    with pytest.raises(ValueError):preflight.verify_database_role(Connection(),policy)

def test_custom_named_production_dsn_and_exchange_secret_are_blocked():
    for environment in ({'CUSTOM_CONNECTION':'postgresql://fixture:fixture@198.51.100.1/production'},
                        {'SOMETHING':'host=remote dbname=production user=operator'},
                        {'BINANCE_API_SECRET':'fixture'}):
        with pytest.raises(ValueError):h.check_process_environment(environment)
