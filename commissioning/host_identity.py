"""Specific Windows-installation authorization; no hostname bypass or public raw IDs.

Protects against accidental wrong-host/user/source and stale approval. A malicious
local administrator/operator executing arbitrary code is outside this boundary.
"""
import base64
import ctypes
import hashlib
import hmac
import json
import ntpath
import os
from pathlib import Path
import platform
import re
import secrets
import subprocess
import time

IDENTITY_FIELDS = ('hostname', 'username', 'sid', 'machine_guid', 'install_id', 'hardware_uuid')
TARGET_HOST = 'ADMINIT-JQ1IQSV'
TARGET_USER = r'ADMINIT-JQ1IQSV\Administrator'
TARGET_EXE = r'C:\Users\Administrator\AppData\Local\MetaScalp\current\MetaScalp.exe'
TARGET_EXE_SHA256 = '9f55837fafbf42b713ebe9206a23afb39ff5ff6de4911d676e7840ae657088df'
COLLECTOR_VERSION = 'adminit-process-evidence-v3-service-contracts'


class DiagnosticError(ValueError):
    """Only fixed safe reason codes cross the public error boundary."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def is_elevated():
    if platform.system() != 'Windows':
        return False
    from ctypes import wintypes
    try:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        security = ctypes.WinDLL('advapi32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        security.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        security.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        token = wintypes.HANDLE()
        if not security.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
            return False
        try:
            elevated = wintypes.DWORD()
            size = wintypes.DWORD()
            return bool(security.GetTokenInformation(token, 20, ctypes.byref(elevated), ctypes.sizeof(elevated), ctypes.byref(size)) and size.value == ctypes.sizeof(elevated) and elevated.value == 1)
        finally:
            kernel.CloseHandle(token)
    except (OSError, AttributeError):
        return False


def system_directory():
    directory = ctypes.create_unicode_buffer(32768)
    if not ctypes.windll.kernel32.GetSystemDirectoryW(directory, len(directory)):
        raise DiagnosticError('WINDOWS_SYSTEM_DIRECTORY_UNAVAILABLE')
    return Path(directory.value)


def collector_identity(expected_sha, *, root=None, manifest=None, manifest_sha256=None):
    """Bind source before/after collection; never trust an operator SHA alone."""
    root = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    if not re.fullmatch('[0-9a-f]{40}', expected_sha or ''):
        raise DiagnosticError('COLLECTOR_SOURCE_UNVERIFIED')
    if manifest or manifest_sha256:
        from preflight import verify_manifest
        if not manifest or not manifest_sha256 or verify_manifest(manifest, expected_sha, manifest_sha256) != root.resolve():
            raise DiagnosticError('COLLECTOR_SOURCE_UNVERIFIED')
    else:
        try:
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()
            if git('rev-parse', 'HEAD') != expected_sha or git('status', '--porcelain', '--untracked-files=all'):
                raise DiagnosticError('COLLECTOR_SOURCE_UNVERIFIED')
        except (OSError, subprocess.SubprocessError, UnicodeError):
            raise DiagnosticError('COLLECTOR_SOURCE_UNVERIFIED') from None
    hashes = {}
    for path in sorted((root/'commissioning').rglob('*')):
        if path.is_file() and path.suffix in ('.py', '.ps1'):
            if any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for p in (path, *path.parents)):
                raise DiagnosticError('COLLECTOR_SOURCE_UNVERIFIED')
            hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not {'commissioning/'+name for name in ('host_identity.py','process_identity.py','host-facts.ps1','process-evidence.ps1')}.issubset(hashes):
        raise DiagnosticError('COLLECTOR_SOURCE_UNVERIFIED')
    return dict(version=COLLECTOR_VERSION, candidate_sha=expected_sha, source_hashes=hashes)


def http_sys_owner(text, port):
    """Fail closed on unknown/localized netsh format or shared/ambiguous queue."""
    owners = []
    for block in re.split(r'(?m)^Request queue name:', text)[1:]:
        urls = re.findall(r'(?im)^\s+(HTTP://\S+)', block)
        if not any(re.search(rf':{port}(?::|/)', url) for url in urls):
            continue
        if any(not re.fullmatch(rf'HTTP://127\.0\.0\.1:{port}(?::127\.0\.0\.1)?/', url, re.I) for url in urls):
            raise ValueError('HTTP.sys endpoint is not exclusive loopback')
        count = re.search(r'Number of active processes attached:\s*(\d+)', block)
        ids = re.findall(r'(?m)^\s+ID:\s*(\d+), image:', block)
        if not count or count[1] != '1' or len(ids) != 1:
            raise ValueError('HTTP.sys queue ownership is ambiguous')
        owners.append(int(ids[0]))
    if len(owners) != 1:
        raise ValueError('exact HTTP.sys API queue not established')
    return owners[0]


def target_identity(facts):
    if (facts['identity']['hostname'].casefold(), facts['identity']['username'].casefold()) != (TARGET_HOST.casefold(), TARGET_USER.casefold()):
        raise ValueError('this enrollment is restricted to ADMINIT-JQ1IQSV Administrator')


def fingerprint(facts, salt):
    identity = facts['identity']
    if any(identity.get(k) is None or not str(identity.get(k, '')).strip() for k in IDENTITY_FIELDS):
        raise ValueError('incomplete host identity')
    hardware = str(identity['hardware_uuid']).replace('-', '').strip().lower()
    if hardware in ('0' * 32, 'f' * 32):
        raise ValueError('unusable hardware identity')
    canonical = json.dumps({k: str(identity[k]).strip().casefold() for k in IDENTITY_FIELDS}, sort_keys=True)
    return hmac.new(bytes.fromhex(salt), b'meta-commission-host-v1\0' + canonical.encode(), hashlib.sha256).hexdigest()


def safe_inventory(facts):
    if facts.get('collector_elevated') is not True:
        raise DiagnosticError('ELEVATED_TOKEN_REQUIRED')
    grid = facts['grid']
    if grid.get('coverage_complete') is not True or grid.get('errors') or grid.get('findings'):
        raise ValueError('Grid/conflict inventory is not clear and complete')
    if grid.get('unknown_process_paths',0) or facts.get('process_inventory',{}).get('unknown_process_paths',0):
        raise ValueError('unresolved process identities')
    if facts.get('credential_names') or facts.get('production_dsn_names'):
        raise ValueError('credentials or production environment requires operator review')
    os_info = facts['os']
    if os_info['system'] != 'Windows' or int(os_info['build']) < 22000 or not os_info['edition'].startswith('Professional'):
        raise ValueError('Windows11 Pro required')


def check_process_environment(environment):
    for key,value in environment.items():
        if not value: continue
        if re.search(r'^(API_KEY|API_SECRET)$|(?:BYBIT|BINANCE|OKX|KUCOIN|COINBASE|EXCHANGE).*(?:KEY|SECRET|TOKEN)',key,re.I):
            raise ValueError('exchange credentials are forbidden')
        if key!='META_ANALYSE_COMMISSIONING_DSN' and (re.search(r'DSN|DATABASE_URL|GRID.*(?:DATABASE|DB_|PG)|^PG(?:HOST|PORT|DATABASE|USER|PASSWORD|SERVICE|OPTIONS|PASSFILE|SSLMODE)',key,re.I) or
                re.search(r'^postgres(?:ql)?://|(?:^|\s)(?:host|dbname|user|password)=',str(value),re.I)):
            raise ValueError('unapproved database environment; values are not published')


def make_policy(facts, *, salt, candidate_sha, manifest_sha256, dbname, user, port,
                data_directory, metascalp, operator_approved, confirm_no_grid, now=None):
    safe_inventory(facts)
    target_identity(facts)
    if operator_approved is not True or confirm_no_grid is not True:
        raise ValueError('explicit operator approval and no-Grid attestation required')
    if not all(re.fullmatch(r'meta_commission_[a-z0-9_]+', v) for v in (dbname, user)):
        raise ValueError('dedicated session database and role required')
    if not re.fullmatch(r'[0-9a-f]{40}', candidate_sha) or not re.fullmatch(r'[0-9a-f]{64}', manifest_sha256):
        raise ValueError('full candidate and trusted manifest hashes required')
    if int(port) != 55480 or not ntpath.isabs(data_directory):
        raise ValueError('explicit nonprivileged port and absolute private cluster directory required')
    installed=validate_metascalp(facts,metascalp['path'])
    if installed['sha256']!=metascalp['sha256']:
        raise ValueError('operator-approved MetaScalp software hash mismatch')
    issued = time.time() if now is None else now
    return dict(schema=1, enrollment_id=secrets.token_hex(16), salt=salt,
                fingerprint=fingerprint(facts, salt), candidate_sha=candidate_sha,
                manifest_sha256=manifest_sha256, operator_approved=True, confirm_no_grid=True,
                issued_at=issued, expires_at=issued + 86400, allowed_stage='smoke30',
                metascalp=dict(path=metascalp['path'],**installed),database=dict(
                    dbname=dbname, user=user, port=int(port), data_directory=data_directory))


def validate_policy(facts, policy, *, expected_name, candidate_sha, manifest_sha256, now=None):
    safe_inventory(facts)
    target_identity(facts)
    db = policy['database']
    if db['port'] != 55480 or not all(re.fullmatch(r'meta_commission_[a-z0-9_]+', db[k]) for k in ('dbname', 'user')):
        raise ValueError('target private database binding required')
    if validate_metascalp(facts, policy['metascalp']['path']) != {k: v for k, v in policy['metascalp'].items() if k != 'path'}:
        raise ValueError('MetaScalp process changed; fresh enrollment required')
    current = time.time() if now is None else now
    if policy.get('schema') != 1 or policy.get('operator_approved') is not True or policy.get('confirm_no_grid') is not True:
        raise ValueError('invalid private operator authorization')
    if policy.get('allowed_stage')!='smoke30': raise ValueError('only supervised30-minute admission is supported')
    if not policy['issued_at'] <= current <= policy['expires_at'] or policy['expires_at'] - policy['issued_at'] > 86400:
        raise ValueError('expired or future authorization')
    if not hmac.compare_digest(fingerprint(facts, policy['salt']), policy['fingerprint']):
        raise ValueError('Windows installation/hardware/user identity mismatch')
    if facts['identity']['hostname'].casefold() != expected_name.casefold():
        raise ValueError('unexpected computer')
    if policy['candidate_sha'] != candidate_sha or policy['manifest_sha256'] != manifest_sha256:
        raise ValueError('authorization source binding mismatch')
    return facts['identity']['hostname']


def public_report(facts, salt):
    return dict(host_fingerprint=fingerprint(facts, salt), os={k:facts['os'][k] for k in ('system','edition','build')},
                grid_findings=len(facts['grid']['findings']), inventory_errors=len(facts['grid']['errors']),
                coverage_complete=facts['grid']['coverage_complete'],
                credential_variable_count=len(facts.get('credential_names', [])),
                production_dsn_variable_count=len(facts.get('production_dsn_names', [])),
                inventory={k:facts['grid'][k] for k in ('coverage_complete','visible_services','visible_tasks','visible_processes',
                    'missing_process_paths','verified_missing_process_paths','unknown_process_paths','reason_counts') if k in facts['grid']},
                postgres_listeners=[{k:p[k] for k in ('port','address')} for p in facts.get('postgres_listeners',[])],
                api_identity_established=bool(facts.get('api_listeners')),
                status='OBSERVATION_ONLY_NOT_AUTHORIZATION')


def collect_facts():
    if platform.system() != 'Windows':
        raise ValueError('Windows host collection required')
    if not is_elevated():
        raise DiagnosticError('ELEVATED_TOKEN_REQUIRED')
    directory = system_directory()
    shell = str(directory / 'WindowsPowerShell/v1.0/powershell.exe')
    environment=dict(os.environ)
    # Do not inherit PowerShell7 module paths into the Windows PowerShell child.
    environment['PSModulePath']=str(directory/'WindowsPowerShell/v1.0/Modules')
    result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
                             str(Path(__file__).with_name('host-facts.ps1'))],
                            capture_output=True, timeout=90,env=environment)
    if result.returncode:
        raise ValueError('host facts unavailable; no private output published')
    facts = json.loads(result.stdout.decode('utf-8-sig'))
    if facts.get('collector_elevated') is not True:
        raise DiagnosticError('ELEVATED_TOKEN_REQUIRED')
    from process_identity import assess_processes
    original_processes=facts['private_inventory']['processes']
    if not original_processes or len(original_processes)!=facts['grid']['visible_processes'] or len({p['ProcessId'] for p in original_processes})!=len(original_processes):
        facts['grid']['errors'].append('Process snapshot incomplete')
        facts['grid']['coverage_complete']=False
    expected_missing=[p['ProcessId'] for p in original_processes if not p.get('ExecutablePath')]
    private = facts['private_inventory']
    private['process_evidence'] = facts.pop('process_evidence')
    private['process_roots'] = facts.pop('process_roots')
    assessment=assess_processes(private['process_evidence'],private['process_roots'],expected_missing)
    facts['process_inventory']=assessment
    facts['grid'].update({k:v for k,v in assessment.items() if k!='results'})
    if assessment['unknown_process_paths']:
        facts['grid']['errors'].append('Some process identities unresolved')
        facts['grid']['coverage_complete']=False
    if 'GRID_PROCESS_INDICATOR' in assessment['reason_counts']:
        facts['grid']['findings'].append('Grid indicator in native process identity')
    state = facts.pop('http_sys_state')
    processes = facts.pop('terminal_processes')
    try:
        owner = http_sys_owner(state, 17845)
        matches = [p for p in processes if p['pid'] == owner]
        if len(matches) != 1: raise ValueError('HTTP.sys owner process unavailable')
        facts['api_listeners'] = [dict(port=17845, address='127.0.0.1', **matches[0])]
    except ValueError:
        facts['api_listeners'] = []
        facts['grid']['errors'].append('HTTP.sys owner identity incomplete')
        facts['grid']['coverage_complete'] = False
    return facts


def dpapi(data, *, decrypt=False):
    if platform.system() != 'Windows':
        raise ValueError('private authorization requires Windows DPAPI CurrentUser')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    library = ctypes.WinDLL('crypt32', use_last_error=True)
    operation = library.CryptUnprotectData if decrypt else library.CryptProtectData
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError('private authorization cannot be decrypted on this Windows user/installation')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        free = ctypes.WinDLL('kernel32').LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(target.data)


def save_private(filename, value):
    path = Path(filename)
    if path.resolve().is_relative_to(Path(__file__).resolve().parent.parent):
        raise ValueError('private identity records must be outside source/repository packet')
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = base64.b64encode(dpapi(json.dumps(value).encode()))
    with path.open('xb') as stream:
        stream.write(payload)


def load_private(filename):
    return json.loads(dpapi(base64.b64decode(Path(filename).read_bytes(), validate=True), decrypt=True))


def validate_bound_database(dsn, policy, environment):
    from psycopg.conninfo import conninfo_to_dict
    if any(v and k.upper().startswith('PG') for k, v in environment.items()):
        raise ValueError('implicit libpq environment is forbidden for commissioning')
    config = conninfo_to_dict(dsn)
    if set(config) - {'host', 'hostaddr', 'port', 'dbname', 'user', 'password', 'connect_timeout'}:
        raise ValueError('unapproved database connection option')
    db = policy['database']
    if config.get('host') not in ('127.0.0.1', '::1', 'localhost'):
        raise ValueError('loopback database required')
    if config.get('hostaddr') not in (None, '127.0.0.1', '::1'):
        raise ValueError('non-loopback hostaddr')
    if config.get('dbname') != db['dbname'] or config.get('user') != db['user'] or int(config.get('port', 0)) != db['port']:
        raise ValueError('database/role/port does not match private authorization')
    config['hostaddr'] = config.get('hostaddr') or ('127.0.0.1' if config['host'] == 'localhost' else config['host'])
    config['connect_timeout'] = '5'
    return config


def validate_cluster_listener(facts, policy):
    db = policy['database']
    listeners = [p for p in facts['postgres_listeners'] if p['port'] == db['port']]
    if not listeners or any(p['address'] not in ('127.0.0.1', '::1') or
                            ntpath.normcase(ntpath.normpath(p.get('data_directory', ''))) !=
                            ntpath.normcase(ntpath.normpath(db['data_directory'])) for p in listeners):
        raise ValueError('approved private loopback cluster not established')


def require_preflight(evidence):
    if any(evidence.get(key) != 'PASS' for key in ('postgres', 'metascalp', 'tls')):
        raise ValueError('PostgreSQL, MetaScalp API/signature and verified TLS must all pass')


def validate_metascalp(facts, executable):
    if ntpath.normcase(ntpath.normpath(str(executable))) != ntpath.normcase(TARGET_EXE):
        raise ValueError('exact reviewed MetaScalp path required')
    matches = [m for m in facts.get('metascalp', []) if
               ntpath.normcase(ntpath.normpath(m['path'])) == ntpath.normcase(ntpath.normpath(str(executable)))
               and m['signature'] == 'Valid']
    if len(matches) != 1:
        raise ValueError('installed signed MetaScalp executable not established')
    item = matches[0]
    if item['sha256'] != TARGET_EXE_SHA256 or not re.search(r'(?:^|,\s*)CN=Grigoryan Construct LLC(?:,|$)', item.get('publisher', '')):
        raise ValueError('exact reviewed MetaScalp hash/publisher required')
    ports = [p for p in facts.get('api_listeners', []) if
             p['address'] == '127.0.0.1' and p['port'] == 17845 and p['exe_sha256'] == item['sha256']
             and p.get('pid') and p.get('process_started') and ntpath.normcase(ntpath.normpath(p.get('exe_path', ''))) == ntpath.normcase(TARGET_EXE)]
    if not ports:
        raise ValueError('signed MetaScalp does not own a loopback API listener')
    if len(ports) != 1: raise ValueError('ambiguous MetaScalp listener')
    return dict(sha256=item['sha256'], file_version=item.get('file_version'), port=17845,
                pid=ports[0]['pid'], process_started=ports[0]['process_started'])


def authorize(args, facts=None):
    import sys
    from preflight import verify_manifest
    if sys.version_info[:2] != (3, 12):
        raise ValueError('Python3.12 required')
    root = verify_manifest(args.manifest, args.expected_sha, args.manifest_sha256)
    if root!=Path(__file__).resolve().parent.parent:
        raise ValueError('executing guard/install source differs from verified packet')
    check_process_environment(os.environ)
    facts = collect_facts() if facts is None else facts
    policy = load_private(args.enrollment)
    name = validate_policy(facts, policy, expected_name=args.expected_computer,
                           candidate_sha=args.expected_sha, manifest_sha256=args.manifest_sha256)
    return root, name, policy, facts


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    diagnostic = sub.add_parser('diagnose')
    diagnostic.add_argument('--output', required=True)
    diagnostic.add_argument('--private-observation', required=True)
    diagnostic.add_argument('--expected-sha', required=True)
    diagnostic.add_argument('--manifest')
    diagnostic.add_argument('--manifest-sha256')
    enrollment = sub.add_parser('enroll')
    for key in ('private-observation', 'enrollment', 'manifest', 'expected-sha', 'manifest-sha256',
                'database', 'role', 'port', 'data-directory','metascalp-exe','metascalp-sha256'):
        enrollment.add_argument('--' + key, required=True)
    enrollment.add_argument('--operator-approved', action='store_true', required=True)
    enrollment.add_argument('--confirm-no-grid', action='store_true', required=True)
    check = sub.add_parser('check')
    for key in ('enrollment', 'manifest', 'expected-sha', 'manifest-sha256', 'expected-computer'):
        check.add_argument('--' + key, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'check':
            authorize(args)
            print('Specific Windows installation/user/source authorization PASS')
            return 0
        if not is_elevated():
            raise DiagnosticError('ELEVATED_TOKEN_REQUIRED')
        collector = collector_identity(args.expected_sha, manifest=args.manifest, manifest_sha256=args.manifest_sha256)
        facts = collect_facts()
        if collector != collector_identity(args.expected_sha, manifest=args.manifest, manifest_sha256=args.manifest_sha256):
            raise DiagnosticError('COLLECTOR_SOURCE_CHANGED')
        if args.command == 'diagnose':
            salt = secrets.token_hex(32)
            report = public_report(facts, salt)
            reasons=[]
            if facts['grid'].get('coverage_complete') is not True or facts['grid'].get('errors'):reasons.append('INCOMPLETE_INVENTORY')
            if facts['grid'].get('findings'):reasons.append('GRID_CONFLICT')
            if facts.get('credential_names') or facts.get('production_dsn_names'):reasons.append('UNAPPROVED_ENVIRONMENT')
            # This is an expected admission rejection, not an unexplained crash
            # after a seemingly successful report. Never include exception text.
            try: safe_inventory(facts)
            except ValueError:
                if not reasons:reasons.append('INVENTORY_POLICY_REJECTED')
            report.update(diagnostic_status='FAIL_CLOSED' if reasons else 'PASS_OBSERVATION_ONLY',reason_codes=reasons)
            save_private(args.private_observation, dict(schema=2, collector=dict(**collector,elevated=True), salt=salt,
                         fingerprint=fingerprint(facts, salt), observed_at=time.time(), facts=facts))
            Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report, indent=2))
            return 1 if reasons else 0
        from preflight import verify_manifest
        root=verify_manifest(args.manifest, args.expected_sha, args.manifest_sha256)
        if root!=Path(__file__).resolve().parent.parent: raise ValueError('executing guard differs from packet')
        observed = load_private(args.private_observation)
        if observed.get('schema') != 2 or observed.get('collector') != dict(**collector,elevated=True):
            raise DiagnosticError('OBSERVATION_COLLECTOR_MISMATCH')
        if not 0 <= time.time() - observed['observed_at'] <= 3600:
            raise ValueError('fresh private host observation required')
        if not hmac.compare_digest(fingerprint(facts, observed['salt']), observed['fingerprint']):
            raise ValueError('observation belongs to another installation/user')
        policy = make_policy(facts, salt=observed['salt'], candidate_sha=args.expected_sha,
                             manifest_sha256=args.manifest_sha256, dbname=args.database, user=args.role,
                             port=int(args.port), data_directory=args.data_directory,
                             metascalp=dict(path=args.metascalp_exe,sha256=args.metascalp_sha256),
                             operator_approved=args.operator_approved, confirm_no_grid=args.confirm_no_grid)
        save_private(args.enrollment, policy)
        print('Private specific-host authorization created; this does not authorize automatic testing')
        return 0
    except Exception as exc:
        failure = dict(status='FAIL_CLOSED', diagnostic_status='FAIL_CLOSED',
                       reason_codes=[exc.code if isinstance(exc,DiagnosticError) else 'DIAGNOSTIC_UNAVAILABLE'],
                       detail='private identity/configuration values are not published')
        if args.command == 'diagnose':
            try: Path(args.output).write_text(json.dumps(failure,indent=2),encoding='utf-8')
            except OSError: pass
        print(json.dumps(failure))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
