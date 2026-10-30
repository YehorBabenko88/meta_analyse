"""Read-only S1 precheck worker. Requires the separately reviewed supervisor."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

SHA = 'b00c66776b27e929016f7541329c29c9349dddfe'
TREE = '0418dc7bea4bb2f40f6712b0f3c0c1a6c63b8288'
MANIFEST_PIN = '804d559d14319fd4d747c8de78cd694b4dc7be2bf38e38fa665f9611c25db74d'
ENV_KEYS = {'PATH', 'GIT_CONFIG_SYSTEM', 'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_NOSYSTEM',
            'PYTHONHOME', 'PYTHONPATH', 'PYTHONSTARTUP', 'PYTHONUSERBASE', '__PYVENV_LAUNCHER__'}
REQUIRED_ROLES = {'python_exe', 'python312_dll', 'hashlib_pyd', 'ctypes_pyd', 'libcrypto',
                  'libffi', 'crt', 'bz2_pyd', 'lzma_pyd', 'git_exe', 'git_core',
                  'libiconv', 'libintl', 'pcre2', 'zlib', 'powershell_exe'}
OPTIONAL_ROLES = {'crt_1'}


class Refusal(Exception):
    def __init__(self, reason, failed=False):
        self.reason = reason
        self.failed = failed


def need(ok, reason='PRECONDITIONS_REQUIRED', failed=False):
    if not ok:
        raise Refusal(reason, failed)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decode(raw):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            need(k not in out)
            out[k] = v
        return out
    need(type(raw) is bytes and 0 < len(raw) <= 1024 * 1024)
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda _: need(False))


def hex256(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


class Budget:
    def __init__(self, clock=time.monotonic, max_bytes=128 * 1024 * 1024):
        self.clock = clock
        self.start = clock()
        self.max_bytes = max_bytes
        self.bytes = 0
        self.paths = set()

    def check(self):
        need(self.clock() - self.start < 30, 'BUDGET_EXCEEDED', True)

    def path(self, p):
        self.paths.add(str(p))
        need(len(self.paths) <= 10000, 'BUDGET_EXCEEDED', True)
        self.check()


def ordinary(path, budget, missing=False):
    need(type(path) is str and Path(path).is_absolute(), 'NAMESPACE_UNAVAILABLE')
    p = Path(path)
    need('..' not in p.parts, 'NAMESPACE_UNAVAILABLE')
    if os.name == 'nt':
        need(re.match(r'^[A-Za-z]:\\', path) is not None and ':' not in path[2:],
             'NAMESPACE_UNAVAILABLE')
    found = None
    ancestors = [*reversed(p.parents), p]
    for at in ancestors:
        budget.path(at)
        try:
            found = at.lstat()
        except FileNotFoundError:
            if missing:
                return None
            raise Refusal('NAMESPACE_UNAVAILABLE') from None
        need(not stat.S_ISLNK(found.st_mode) and not (getattr(found, 'st_file_attributes', 0) & 0x400),
             'NAMESPACE_UNAVAILABLE')
        if at != p:
            need(stat.S_ISDIR(found.st_mode), 'NAMESPACE_UNAVAILABLE')
    return found


def read(path, budget, limit=16 * 1024 * 1024, hardlink_safe=False):
    began = budget.clock()
    before = ordinary(path, budget)
    need(stat.S_ISREG(before.st_mode) and (before.st_nlink == 1 or hardlink_safe), 'NAMESPACE_UNAVAILABLE')
    need(before.st_size <= limit, 'BUDGET_EXCEEDED', True)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_nlink)
        need(identity(before) == identity(opened), 'NAMESPACE_UNAVAILABLE')
        chunks = []
        while True:
            budget.check()
            need(budget.clock() - began < 5, 'BUDGET_EXCEEDED', True)
            part = stream.read(min(256 * 1024, limit + 1 - sum(map(len, chunks))))
            if not part:
                break
            chunks.append(part)
            budget.bytes += len(part)
            need(budget.bytes <= budget.max_bytes, 'BUDGET_EXCEEDED', True)
            need(sum(map(len, chunks)) <= limit, 'BUDGET_EXCEEDED', True)
        after = os.fstat(stream.fileno())
    current = ordinary(path, budget)
    need(identity(opened) == identity(after) == identity(current), 'NAMESPACE_UNAVAILABLE')
    data = b''.join(chunks)
    need(len(data) == before.st_size, 'NAMESPACE_UNAVAILABLE')
    budget.check()
    need(budget.clock() - began < 5, 'BUDGET_EXCEEDED', True)
    return data


def check_mapping(raw):
    m = decode(raw)
    need(type(m) is dict and m.get('status') == 'PASS' and m.get('reference_integrity') == 'PASS',
         'RUNTIME_CONTINUITY_UNAVAILABLE')
    for key, expected in {'vendor_files_matched': 2397, 'additional_native_matched': 2,
                          'runtime_delta_reused': 1, 'loader_safety_established': 0,
                          's0_authorized': 0, 'stop_required': 1}.items():
        need(type(m.get(key)) is int and m[key] == expected, 'RUNTIME_CONTINUITY_UNAVAILABLE')
    for key in ('import_shadow_blocked', 'required_missing', 'unreferenced', 'mismatched',
                'cache_blocked', 'cache_bad_header', 'cache_bad_body', 'errors'):
        need(type(m.get(key)) is int and m[key] == 0, 'RUNTIME_CONTINUITY_UNAVAILABLE')
    need(type(m.get('cache_files')) is int and 0 <= m['cache_files'] <= 50000 and
         type(m.get('cache_matched')) is int and m['cache_matched'] == m['cache_files'],
         'RUNTIME_CONTINUITY_UNAVAILABLE')


def base_receipt():
    return dict(schema=1, stage='S1_PRECHECK', contract_version=1, source_sha=SHA, source_tree=TREE,
                source_bound=False, source_continuity='NOT_EVALUATED',
                runtime_continuity='NOT_EVALUATED', output_readiness='NOT_EVALUATED',
                outcome='BLOCKED', reason='PRECONDITIONS_REQUIRED', elapsed_ms=0, exit_code=2,
                attempts=0, s1_complete=False, authorization='NONE', g0_status='FAIL_CLOSED',
                next_stage='BLOCKED', stop_required=True)


def evaluate(*, repo, packet_raw, packet_pin, manifest_raw, environment=None,
             operator_approved=False, output_ready=True, clock=time.monotonic,
             max_bytes=128 * 1024 * 1024, active_python=None, active_shell=None):
    r = base_receipt()
    b = Budget(clock, max_bytes)
    try:
        need(operator_approved is True)
        r['attempts'] = 1
        need(output_ready is True, 'OUTPUT_UNAVAILABLE')
        need(hex256(packet_pin) and type(packet_raw) is bytes and digest(packet_raw) == packet_pin)
        need(type(manifest_raw) is bytes and digest(manifest_raw) == MANIFEST_PIN)
        packet = decode(packet_raw)
        manifest = decode(manifest_raw)
        need(type(packet) is dict and set(packet) == {'schema', 'reference_kind', 'source_sha',
             'source_tree', 'mapping_receipt', 'files', 'absent', 'environment'})
        need(type(packet['schema']) is int and packet['schema'] == 1 and
             packet['reference_kind'] == 'EXTERNALLY_REVIEWED_CONTINUITY' and
             packet['source_sha'] == SHA and packet['source_tree'] == TREE)
        need(type(manifest) is dict and set(manifest) == {'schema', 'sha', 'tree', 'files'} and
             type(manifest['schema']) is int and manifest['schema'] == 1 and
             manifest['sha'] == SHA and manifest['tree'] == TREE)
        files = manifest['files']
        need(type(files) is dict and 1 <= len(files) <= 10000)
        ordinary(repo, b)

        def bind_source():
            for name, expected in files.items():
                need(type(name) is str and name and '\\' not in name and ':' not in name and
                     all(v not in ('', '.', '..') for v in name.split('/')) and hex256(expected))
                path = str(Path(repo).joinpath(*name.split('/')))
                need(digest(read(path, b)) == expected, 'SOURCE_CHANGED', True)

        bind_source()
        r['source_continuity'] = 'PASS'
        entries = packet['files']
        need(type(entries) is list and len(REQUIRED_ROLES) <= len(entries) <= 32)
        roles = set()
        for entry in entries:
            need(type(entry) is dict and set(entry) == {'role', 'path', 'sha256'})
            role = entry['role']
            need(type(role) is str and role in REQUIRED_ROLES | OPTIONAL_ROLES and role not in roles)
            roles.add(role)
            need(hex256(entry['sha256']))
            if role == 'python_exe' and active_python is not None:
                need(os.path.normcase(entry['path']) == os.path.normcase(active_python),
                     'RUNTIME_CONTINUITY_UNAVAILABLE')
            if role == 'powershell_exe' and active_shell is not None:
                need(os.path.normcase(entry['path']) == os.path.normcase(active_shell),
                     'RUNTIME_CONTINUITY_UNAVAILABLE')
            need(digest(read(entry['path'], b, hardlink_safe=True)) == entry['sha256'],
                 'RUNTIME_CONTINUITY_UNAVAILABLE', True)
        need(REQUIRED_ROLES <= roles)
        need(type(packet['absent']) is list and 1 <= len(packet['absent']) <= 16)
        for p in packet['absent']:
            need(ordinary(p, b, missing=True) is None, 'RUNTIME_CONTINUITY_UNAVAILABLE', True)
        expected_env = packet['environment']
        env = os.environ if environment is None else environment
        need(type(expected_env) is dict and set(expected_env) == ENV_KEYS)
        need(all(v is None or type(v) is str for v in expected_env.values()))
        need(all(env.get(k) == v for k, v in expected_env.items()), 'RUNTIME_CONTINUITY_UNAVAILABLE')
        need(not any(k.upper().startswith('GIT_') and k.upper() not in ENV_KEYS for k in env),
             'RUNTIME_CONTINUITY_UNAVAILABLE')
        mapping = packet['mapping_receipt']
        need(type(mapping) is dict and set(mapping) == {'path', 'sha256'} and hex256(mapping['sha256']))
        raw = read(mapping['path'], b, 4096)
        need(digest(raw) == mapping['sha256'], 'RUNTIME_CONTINUITY_UNAVAILABLE')
        check_mapping(raw)
        r['runtime_continuity'] = 'PASS'
        bind_source()
        # Rebind selected runtime state after the final source scan. This still is
        # a snapshot, not continuous hostile-writer exclusion.
        for entry in entries:
            need(digest(read(entry['path'], b, hardlink_safe=True)) == entry['sha256'],
                 'RUNTIME_CONTINUITY_UNAVAILABLE', True)
        for p in packet['absent']:
            need(ordinary(p, b, missing=True) is None, 'RUNTIME_CONTINUITY_UNAVAILABLE', True)
        need(all(env.get(k) == v for k, v in expected_env.items()), 'RUNTIME_CONTINUITY_UNAVAILABLE')
        need(digest(read(mapping['path'], b, 4096)) == mapping['sha256'],
             'RUNTIME_CONTINUITY_UNAVAILABLE')
        b.check()
        r.update(source_bound=True, output_readiness='PASS', outcome='PASS_PRECHECK_ONLY',
                 reason='PRECHECK_COMPLETE', exit_code=0)
    except Refusal as exc:
        r.update(reason=exc.reason, outcome='FAIL' if exc.failed else 'BLOCKED',
                 exit_code=1 if exc.failed else 2, source_bound=False)
    except Exception:
        r.update(reason='PRECONDITIONS_REQUIRED', source_bound=False)
    finally:
        r['elapsed_ms'] = max(0, int((clock() - b.start) * 1000))
    return r


def audit_no_children(event, _args):
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.fork',
                 'os.exec', 'os.spawn', 'pty.spawn', '_winapi.CreateProcess',
                 'ctypes.dlopen', 'socket.__new__'}:
        raise Refusal('PRECONDITIONS_REQUIRED')


def main(argv=None):
    class PrivateParser(argparse.ArgumentParser):
        def error(self, _message):
            raise Refusal('PRECONDITIONS_REQUIRED')
    r = base_receipt()
    try:
        sys.addaudithook(audit_no_children)
        identity = sys.stdin.buffer.readline(32)
        need(identity.endswith(b'\n') and identity.strip().isdigit() and
             int(identity) == os.getpid())
        p = PrivateParser(add_help=False)
        for key in ('repo', 'packet', 'packet-pin', 'shell'):
            p.add_argument('--' + key, required=True)
        p.add_argument('--operator-approved', action='store_true')
        args = p.parse_args(argv)
        need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode)
        b = Budget()
        packet = read(args.packet, b, 1024 * 1024)
        manifest = read(str(Path(__file__).with_name('s1_source_reference.json')), b, 1024 * 1024)
        r = evaluate(repo=args.repo, packet_raw=packet, packet_pin=args.packet_pin,
                     manifest_raw=manifest, operator_approved=args.operator_approved,
                     active_python=sys.executable, active_shell=args.shell)
    except Exception:
        pass
    raw = json.dumps(r, sort_keys=True, allow_nan=False, separators=(',', ':'))
    need(len(raw.encode()) <= 4096, 'OUTPUT_UNAVAILABLE')
    try:
        sys.stdout.write(raw + '\n')
        sys.stdout.flush()
        # Supervisor must sample completed-work resource state before release.
        # Unexpected EOF/release is a refusal, never a standalone worker PASS.
        release = sys.stdin.buffer.readline(128)
        nonce = release.strip()
        if not release.endswith(b'\n') or re.fullmatch(b'[0-9a-f]{32}', nonce) is None:
            return 2
        sys.stdout.write('S1_ACK:' + nonce.decode('ascii') + '\n')
        sys.stdout.flush()
    except Exception:
        return 2
    return r['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
