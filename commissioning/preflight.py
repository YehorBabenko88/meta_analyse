"""Read-only target-PC preflight; never installs, migrates or changes CA trust."""
import argparse, asyncio, hashlib, json, os, platform, ssl, sys, hmac
from pathlib import Path
from datetime import datetime, timezone


def verify_manifest(filename, expected_sha, manifest_sha256):
    raw=Path(filename).read_bytes()
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(),manifest_sha256):
        raise ValueError('trusted manifest digest mismatch')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result: raise ValueError('duplicate manifest JSON key')
            result[key]=value
        return result
    manifest=json.loads(raw,object_pairs_hook=unique)
    if manifest['candidate_sha']!=expected_sha: raise ValueError('candidate SHA mismatch')
    parent=Path(filename).resolve().parent
    relative=Path(manifest['source_root'])
    if relative.is_absolute() or '..' in relative.parts: raise ValueError('invalid source root')
    root=(parent/relative).resolve()
    if not root.is_relative_to(parent): raise ValueError('source root escapes packet')
    required={'pyproject.toml','requirements.lock','commissioning/host_identity.py','commissioning/host-facts.ps1',
              'commissioning/preflight.py','commissioning/run_readonly.py','src/meta_analyse/desktop.py'}
    recorded=set()
    for item in manifest['files']:
        path=Path(item['path'])
        if path.is_absolute() or '..' in path.parts or item['path'] in recorded: raise ValueError('invalid/duplicate manifest path')
        recorded.add(item['path'])
        original=root/path
        for component in (original,*original.parents):
            if component==parent: break
            if component.is_symlink() or (hasattr(component,'is_junction') and component.is_junction()):
                raise ValueError('source reparse point is not allowed')
        file=original.resolve()
        if not file.is_relative_to(root): raise ValueError('manifest path escapes source')
        if hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']: raise ValueError('source hash mismatch: '+item['path'])
    if not required.issubset(recorded): raise ValueError('required source coverage missing')
    actual={p.relative_to(root).as_posix() for directory in ('src','commissioning') for p in (root/directory).rglob('*') if p.is_file() and p.suffix in ('.py','.ps1')}
    if not actual.issubset(recorded): raise ValueError('unmanifested executable source')
    if (root/'.env').exists(): raise ValueError('unreviewed .env in commissioning source')
    return root


def target_guard(args):
    from host_identity import authorize
    return authorize(args)


def validate_local_database(dsn):
    import ipaddress
    from psycopg.conninfo import conninfo_to_dict
    config=conninfo_to_dict(dsn)
    if config.get('service') or os.environ.get('PGSERVICE') or os.environ.get('PGSERVICEFILE'):
        raise ValueError('commissioning requires a self-contained DSN without service overrides')
    if config.get('host') not in ('127.0.0.1','localhost','::1') or not config.get('dbname','').startswith('meta_commission_'):
        raise ValueError('dedicated loopback commissioning database required')
    address=config.get('hostaddr') or os.environ.get('PGHOSTADDR')
    if address and not ipaddress.ip_address(address).is_loopback:
        raise ValueError('non-loopback hostaddr forbidden')
    config['hostaddr']=address or ('127.0.0.1' if config['host']=='localhost' else config['host'])
    return config


def verify_package_source(root):
    import meta_analyse
    if Path(meta_analyse.__file__).resolve().parent != (root/'src'/'meta_analyse').resolve():
        raise ValueError('installed package does not match verified source root')


def verify_database_role(conn,policy):
    version=int(conn.execute('SHOW server_version_num').fetchone()[0])
    if version != 180001: raise ValueError('PostgreSQL 18.1 exactly required on target')
    db=conn.execute("SELECT current_database(),current_user,session_user,pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()").fetchone()
    bound=policy['database']
    if db!=(bound['dbname'],bound['user'],bound['user'],bound['user']):
        raise ValueError('dedicated database ownership/session identity mismatch')
    privileges=conn.execute('SELECT rolsuper,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls,rolcanlogin FROM pg_roles WHERE rolname=current_user').fetchone()
    if not privileges or any(privileges[:5]) or not privileges[5]: raise ValueError('excessive or unusable test role privileges')
    if conn.execute('SELECT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user))').fetchone()[0]:
        raise ValueError('test role memberships are not allowed')
    if conn.execute("SELECT count(*) FROM pg_database WHERE datallowconn AND datname<>current_database() AND has_database_privilege(current_user,oid,'CONNECT')").fetchone()[0]:
        raise ValueError('test role can connect to other databases via direct/PUBLIC/membership grants')
    return version,db


async def inspect(args):
    import psycopg, PySide6, certifi
    from host_identity import validate_bound_database,validate_cluster_listener,validate_metascalp,require_preflight
    root,name,policy,facts=target_guard(args)
    verify_package_source(root)
    from meta_analyse.exchange import BybitPublic
    exe=Path(args.metascalp_exe)
    if not exe.is_file(): raise ValueError('installed MetaScalp executable not found')
    installed=validate_metascalp(facts,exe)
    approved=policy['metascalp']
    import ntpath
    if installed != {k:v for k,v in approved.items() if k != 'path'} or ntpath.normcase(ntpath.normpath(str(exe)))!=ntpath.normcase(ntpath.normpath(approved['path'])):
        raise ValueError('MetaScalp identity/API endpoint differs from private approval')
    if hashlib.sha256(exe.read_bytes()).hexdigest()!=installed['sha256']:
        raise ValueError('MetaScalp executable changed after signature check')
    validate_cluster_listener(facts,policy)
    config=validate_bound_database(os.environ['META_ANALYSE_COMMISSIONING_DSN'],policy,os.environ)
    with psycopg.connect(**config) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        version,db=verify_database_role(conn,policy)
    result=dict(timestamp=datetime.now(timezone.utc).isoformat(),candidate_sha=args.expected_sha,
        status='PASS',computer=name,host_fingerprint=policy['fingerprint'],enrollment_id=policy['enrollment_id'],
        windows=platform.platform(),python=sys.version,pyside6=PySide6.__version__,
        openssl=ssl.OPENSSL_VERSION,certifi_version=certifi.__version__,postgres_version=version,
        database=db[0],metascalp_exe_sha256=installed['sha256'],metascalp_version=installed['file_version'],
        metascalp_api_port=installed['port'],
        metascalp_pid=installed['pid'],metascalp_process_started=installed['process_started'],
        ca_override_present={k:bool(os.environ.get(k)) for k in ('SSL_CERT_FILE','SSL_CERT_DIR','HTTPS_PROXY','HTTP_PROXY')},
        long_runtime_tests='NOT_RUN')
    from meta_analyse.ports import MetaScalp
    terminal=MetaScalp()
    try:
        response=await terminal.client.get(f"http://127.0.0.1:{installed['port']}/ping")
        response.raise_for_status()
        if response.json() != {'app':'MetaScalp','version':'1.0.291'}:
            raise ValueError('MetaScalp local API contract mismatch')
    finally: await terminal.close()
    from host_identity import collect_facts
    if validate_metascalp(collect_facts(),exe) != installed:
        raise ValueError('MetaScalp process identity changed during ping')
    exchange=BybitPublic()
    try:
        context=exchange.client._transport._pool._ssl_context
        if context.verify_mode!=ssl.CERT_REQUIRED or not context.check_hostname:
            raise ValueError('certificate and hostname verification required')
        response=await exchange.client.get('/v5/market/time');response.raise_for_status()
        if response.json().get('retCode')!=0: raise ValueError('Bybit REST retCode failure')
        tls=response.extensions['network_stream'].get_extra_info('ssl_object')
        result.update(tls_probe='PASS',tls_version=tls.version(),tls_cipher=tls.cipher()[0])
    finally: await exchange.close()
    result.update(postgres='PASS',metascalp='PASS',tls='PASS')
    require_preflight(result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','manifest-sha256','expected-sha','expected-computer','enrollment','metascalp-exe','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--probe-public-rest',action='store_true',help='Compatibility option; verified REST probe is always mandatory')
    a=p.parse_args()
    try: result=asyncio.run(inspect(a));code=0
    except Exception as exc: result=dict(status='FAIL',error_type=type(exc).__name__,long_runtime_tests='NOT_RUN');code=1
    Path(a.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2));return code

if __name__=='__main__':raise SystemExit(main())
