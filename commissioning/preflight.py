"""Read-only target-PC preflight; never installs, migrates or changes CA trust."""
import argparse, asyncio, hashlib, json, os, platform, ssl, sys
from pathlib import Path
from datetime import datetime, timezone


def verify_manifest(filename, expected_sha):
    manifest=json.loads(Path(filename).read_text(encoding='utf-8'))
    if manifest['candidate_sha']!=expected_sha: raise ValueError('candidate SHA mismatch')
    root=Path(manifest['source_root']).resolve() if Path(manifest['source_root']).is_absolute() else (Path(filename).resolve().parent/manifest['source_root']).resolve()
    for item in manifest['files']:
        file=(root/item['path']).resolve()
        if not file.is_relative_to(root): raise ValueError('manifest path escapes source')
        if hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']: raise ValueError('source hash mismatch: '+item['path'])
    return root


def target_guard(expected_name):
    name=os.environ.get('COMPUTERNAME',platform.node())
    if name.casefold()!=expected_name.casefold(): raise ValueError('unexpected computer')
    if name.upper().replace('-','') in ('LS5','LS7'): raise ValueError('protected production computer')
    if platform.system()!='Windows' or sys.version_info[:2]!=(3,12): raise ValueError('Windows / Python3.12 required')
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion') as key:
        build=int(winreg.QueryValueEx(key,'CurrentBuildNumber')[0])
        edition=winreg.QueryValueEx(key,'EditionID')[0]
    if build<22000 or not edition.startswith('Professional'): raise ValueError('Windows11 Pro required')
    return name


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


async def inspect(args):
    import psycopg, PySide6, certifi
    from psycopg.conninfo import conninfo_to_dict
    name=target_guard(args.expected_computer)
    root=verify_manifest(args.manifest,args.expected_sha)
    verify_package_source(root)
    from meta_analyse.exchange import BybitPublic
    exe=Path(args.metascalp_exe)
    if not exe.is_file(): raise ValueError('installed MetaScalp executable not found')
    config=validate_local_database(os.environ['META_ANALYSE_COMMISSIONING_DSN'])
    config['connect_timeout']='5'
    with psycopg.connect(**config) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        version=int(conn.execute('SHOW server_version_num').fetchone()[0])
        if version//10000!=18: raise ValueError('PostgreSQL18 required on target')
        db=conn.execute('SELECT current_database(),version()').fetchone()
    result=dict(timestamp=datetime.now(timezone.utc).isoformat(),candidate_sha=args.expected_sha,
        computer=name,windows=platform.platform(),python=sys.version,pyside6=PySide6.__version__,
        openssl=ssl.OPENSSL_VERSION,certifi_version=certifi.__version__,postgres_version=db[1],
        database=db[0],metascalp_exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        ca_override_present={k:bool(os.environ.get(k)) for k in ('SSL_CERT_FILE','SSL_CERT_DIR','HTTPS_PROXY','HTTP_PROXY')},
        tls_probe='NOT_RUN',long_runtime_tests='NOT_RUN')
    if args.probe_public_rest:
        exchange=BybitPublic()
        try:
            response=await exchange.client.get('/v5/market/time');response.raise_for_status()
            if response.json().get('retCode')!=0: raise ValueError('Bybit REST retCode failure')
            tls=response.extensions['network_stream'].get_extra_info('ssl_object')
            result.update(tls_probe='PASS',tls_version=tls.version(),tls_cipher=tls.cipher()[0])
        finally: await exchange.close()
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','expected-sha','expected-computer','metascalp-exe','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--probe-public-rest',action='store_true')
    a=p.parse_args()
    try: result=asyncio.run(inspect(a));code=0
    except Exception as exc: result=dict(status='FAIL',error_type=type(exc).__name__,long_runtime_tests='NOT_RUN');code=1
    Path(a.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2));return code

if __name__=='__main__':raise SystemExit(main())
