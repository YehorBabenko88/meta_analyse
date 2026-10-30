"""Synthetic-only S1 continuity and privacy regressions; no production imports."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / 'scripts' / 's1_precheck.py'
spec = importlib.util.spec_from_file_location('s1_test_subject', SCRIPT)
s1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s1)


def digest(b):
    return hashlib.sha256(b).hexdigest()


@pytest.fixture
def case(tmp_path, monkeypatch):
    repo = tmp_path / 'source'
    repo.mkdir()
    (repo / 'sentinel.py').write_bytes(b'# source only\n')
    manifest = json.dumps(dict(schema=1, sha=s1.SHA, tree=s1.TREE,
                              files={'sentinel.py': digest(b'# source only\n')})).encode()
    monkeypatch.setattr(s1, 'MANIFEST_PIN', digest(manifest))
    entries = []
    for role in sorted(s1.REQUIRED_ROLES):
        path = tmp_path / (role + '.bin')
        path.write_bytes(b'VENDOR_REFERENCE_' + role.encode())
        entries.append(dict(role=role, path=str(path), sha256=digest(path.read_bytes())))
    mapping = dict(status='PASS', reference_integrity='PASS', vendor_files_matched=2397,
                   cache_files=313, cache_matched=313, additional_native_matched=2,
                   runtime_delta_reused=1, import_shadow_blocked=0,
                   required_missing=0, unreferenced=0, mismatched=0, cache_blocked=0,
                   cache_bad_header=0, cache_bad_body=0, errors=0,
                   loader_safety_established=0, s0_authorized=0, stop_required=1)
    receipt = tmp_path / 'mapping.json'
    receipt.write_text(json.dumps(mapping))
    packet = dict(schema=1, reference_kind='EXTERNALLY_REVIEWED_CONTINUITY',
                  source_sha=s1.SHA, source_tree=s1.TREE, files=entries,
                  mapping_receipt=dict(path=str(receipt), sha256=digest(receipt.read_bytes())),
                  absent=[str(tmp_path / 'python312._pth')],
                  environment={k: None for k in s1.ENV_KEYS})

    def run(**kw):
        raw = json.dumps(packet).encode()
        args = dict(repo=str(repo), packet_raw=raw, packet_pin=digest(raw),
                    manifest_raw=manifest, environment={}, operator_approved=True)
        args.update(kw)
        return s1.evaluate(**args)

    return repo, packet, run


def test_positive(case):
    _, _, run = case
    r = run()
    assert r['outcome'] == 'PASS_PRECHECK_ONLY'
    assert r['source_bound'] is True
    assert r['authorization'] == 'NONE' and r['g0_status'] == 'FAIL_CLOSED'
    assert r['s1_complete'] is False and r['stop_required'] is True


@pytest.mark.parametrize('field,value', [('operator_approved', False), ('operator_approved', 1),
                                        ('packet_pin', '0' * 64), ('packet_raw', b'{bad'),
                                        ('packet_raw', b'{"schema":1,"schema":1}'),
                                        ('packet_raw', b'{"x":NaN}'), ('manifest_raw', b'{}')])
def test_fail_closed_inputs(case, field, value):
    _, _, run = case
    r = run(**{field: value})
    assert r['outcome'] == 'BLOCKED' and r['exit_code'] == 2


def test_source_change(case):
    repo, _, run = case
    (repo / 'sentinel.py').write_bytes(b'PRIVATE_EXCEPTION_MARKER')
    assert run()['reason'] == 'SOURCE_CHANGED'


def test_runtime_change(case):
    _, packet, run = case
    Path(packet['files'][0]['path']).write_bytes(b'PRIVATE_RUNTIME_MARKER')
    assert run()['reason'] == 'RUNTIME_CONTINUITY_UNAVAILABLE'


@pytest.mark.parametrize('mutate', ['missing', 'bool_schema', 'duplicate_role', 'unknown_role',
                                  'source_sha', 'environment', 'mapping'])
def test_packet_negatives(case, mutate):
    _, packet, run = case
    if mutate == 'missing': packet['files'].pop()
    if mutate == 'bool_schema': packet['schema'] = True
    if mutate == 'duplicate_role': packet['files'].append(packet['files'][0])
    if mutate == 'unknown_role': packet['files'][0]['role'] = 'unreviewed'
    if mutate == 'source_sha': packet['source_sha'] = '0' * 40
    if mutate == 'environment': packet['environment']['GIT_CONFIG_COUNT'] = '2'
    if mutate == 'mapping': Path(packet['mapping_receipt']['path']).write_text('{}')
    assert run()['outcome'] != 'PASS_PRECHECK_ONLY'


def test_startup_file_appears(case):
    _, packet, run = case
    Path(packet['absent'][0]).write_text('unapproved startup')
    assert run()['outcome'] != 'PASS_PRECHECK_ONLY'


def test_environment_override(case):
    _, _, run = case
    assert run(environment={'GIT_TRACE': 'PRIVATE_PATH'})['outcome'] != 'PASS_PRECHECK_ONLY'


def test_timeout(case):
    _, _, run = case
    times = iter([0.0, 31.0])
    assert run(clock=lambda: next(times, 31.0))['reason'] == 'BUDGET_EXCEEDED'


def test_resource_budget(case):
    _, _, run = case
    assert run(max_bytes=1)['reason'] == 'BUDGET_EXCEEDED'


def test_stdout_failure(case):
    _, _, run = case
    assert run(output_ready=False)['outcome'] != 'PASS_PRECHECK_ONLY'


def test_privacy(case):
    repo, packet, run = case
    Path(packet['files'][0]['path']).write_bytes(b'PRIVATE_RUNTIME_MARKER')
    raw = json.dumps(run())
    assert str(repo) not in raw and 'PRIVATE_' not in raw
    assert len(raw.encode()) <= 4096


def test_hardlink(case, tmp_path):
    import os
    repo, _, run = case
    os.link(repo / 'sentinel.py', tmp_path / 'alias')
    assert run()['outcome'] != 'PASS_PRECHECK_ONLY'


@pytest.mark.parametrize('kind', ['symlink', 'reparse'])
def test_link_metadata_blocks_without_privilege(case, monkeypatch, kind):
    import stat
    from types import SimpleNamespace
    repo, _, run = case
    original = Path.lstat
    def lstat(path, *args, **kw):
        info = original(path, *args, **kw)
        if path == repo / 'sentinel.py':
            return SimpleNamespace(st_mode=stat.S_IFLNK if kind == 'symlink' else info.st_mode,
                                   st_file_attributes=0 if kind == 'symlink' else 0x400)
        return info
    monkeypatch.setattr(Path, 'lstat', lstat)
    assert run()['reason'] == 'NAMESPACE_UNAVAILABLE'


def test_no_stage_chaining_source():
    code = SCRIPT.read_text()
    assert 'local_smoke' not in code
    assert 'import subprocess' not in code


@pytest.mark.parametrize('event', ['subprocess.Popen', '_winapi.CreateProcess', 'os.system',
                                  'os.posix_spawn', 'os.fork', 'os.exec', 'os.spawn',
                                  'ctypes.dlopen', 'socket.__new__'])
def test_unexpected_children_and_network_events(event):
    with pytest.raises(s1.Refusal):
        s1.audit_no_children(event, ())


def test_runtime_change_during_final_source_scan(case, monkeypatch):
    repo, packet, run = case
    original = s1.read
    seen = 0
    def read(path, *args, **kw):
        nonlocal seen
        result = original(path, *args, **kw)
        if Path(path) == repo / 'sentinel.py':
            seen += 1
            if seen == 2:
                Path(packet['files'][0]['path']).write_bytes(b'PRIVATE_LATE_CHANGE')
        return result
    monkeypatch.setattr(s1, 'read', read)
    assert run()['reason'] == 'RUNTIME_CONTINUITY_UNAVAILABLE'


def test_manifest_pin_and_supervisor_pin_match():
    raw = SCRIPT.with_name('s1_source_reference.json').read_bytes()
    assert digest(raw) == s1.MANIFEST_PIN
    manifest = json.loads(raw)
    assert len(manifest['files']) == 752
    assert digest(SCRIPT.read_bytes()) in SCRIPT.with_name('Invoke-S1Precheck.ps1').read_text()


def test_no_deadline_expired_launch():
    raw = SCRIPT.with_name('Invoke-S1Precheck.ps1').read_text()
    before_start = raw.split('Need ($child.Start())')[0]
    assert before_start.rstrip().endswith('Need ($watch.Elapsed.TotalSeconds -lt 30)')


def test_missing_operator_cannot_launch_supervisor():
    raw = SCRIPT.with_name('Invoke-S1Precheck.ps1').read_text()
    assert raw.index('$OperatorApproved.IsPresent') < raw.index('$child.Start()')
    assert raw.index('(SHA256 $packetBytes) -ceq $PacketSha256') < raw.index('$child.Start()')


def test_s0_harness_unchanged():
    # Normalize checkout line endings for source comparison; no S0 execution.
    raw = SCRIPT.with_name('local_smoke.py').read_text(encoding='utf-8').encode()
    assert digest(raw) == 'a5892c9f32ca6662af84995eb77e1170b8e69395719da549f3c909169c42e9b5'


def test_malformed_cli_privacy():
    import subprocess
    import sys
    p = subprocess.run([sys.executable, '-I', '-S', '-B', str(SCRIPT), '--PRIVATE_SECRET'],
                       input=b'bad-handshake\n', capture_output=True, timeout=5)
    assert p.returncode == 2 and p.stderr == b'' and b'PRIVATE_' not in p.stdout
    r = json.loads(p.stdout)
    assert r['outcome'] == 'BLOCKED' and r['authorization'] == 'NONE'
