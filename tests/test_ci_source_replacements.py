"""Raw Git identity controls in independent fixture clones, never native admission."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest

SOURCE = Path(__file__).resolve().parents[1]
FILES = ('record_ci_source.py', 'integration_synthetic_boundary.py',
         'check_final_integration_junit.py', 'platform_coverage.py',
         'project_public_ci_evidence.py', 'ci_skip_policy.py')


def fixture(tmp_path, monkeypatch, namespace, kind):
    # Prevent inherited Git path/config overrides from reaching any primary repo.
    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', os.devnull)
    env = dict(os.environ)
    seed, root = tmp_path / 'seed', tmp_path / 'clone'
    seed.mkdir()
    def git(at, *args, raw=True, data=None):
        command = ['git'] + (['--no-replace-objects'] if raw else [])
        return subprocess.check_output(command + ['-c', 'core.hooksPath=' + os.devnull,
            '-c', 'core.autocrlf=false', '-C', str(at), *args], input=data,
            env=env, stderr=subprocess.PIPE, timeout=15).strip()
    git(seed, 'init', '-q')
    (seed / 'scripts').mkdir()
    (seed / 'scripts/__init__.py').write_bytes(b'')
    for name in FILES:
        (seed / 'scripts' / name).write_bytes((SOURCE / 'scripts' / name).read_bytes())
    (seed / '.gitignore').write_bytes(b'__pycache__/\nsource-sha.json\n')
    (seed / 'inert.txt').write_bytes(b'canonical fixture bytes\n')
    git(seed, 'add', '.')
    git(seed, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-qm', 'isolated source fixture')
    git(seed, 'clone', '--no-hardlinks', str(seed), str(root))
    assert (root / '.git').is_dir()
    assert not (root / '.git/objects/info/alternates').exists()
    head = git(root, 'rev-parse', 'HEAD').decode()
    tree = git(root, 'rev-parse', 'HEAD^{tree}').decode()
    original = replacement = None
    if kind == 'blob':
        original = git(root, 'rev-parse', 'HEAD:inert.txt').decode()
        replacement = git(root, 'hash-object', '-w', '--stdin', data=b'virtual inert bytes\n').decode()
    elif kind in ('tree', 'commit'):
        replacement = git(root, 'mktree', data=b'').decode()
        original = tree
        if kind == 'commit':
            original = head
            replacement = git(root, '-c', 'user.name=Fixture', '-c',
                'user.email=fixture@example.invalid', 'commit-tree', replacement,
                '-p', head, data=b'virtual commit\n').decode()
    if original:
        git(root, 'update-ref', namespace + '/' + original, replacement)
    env['GIT_REPLACE_REF_BASE'] = namespace + '/'
    if original:
        # Actual replacement-aware lookup is the witness, not a missing-flag grep.
        assert git(root, 'cat-file', kind, original, raw=False) == git(root, 'cat-file', kind, replacement)
        assert git(root, 'cat-file', kind, original, raw=False) != git(root, 'cat-file', kind, original)
    assert git(root, 'rev-parse', 'HEAD').decode() == head
    assert git(root, 'rev-parse', 'HEAD^{tree}').decode() == tree
    assert git(root, 'status', '--porcelain') == b''
    return SimpleNamespace(root=root, env=env, head=head, tree=tree, git=git)


def run(f, *args, **extra):
    return subprocess.run([sys.executable, '-B', *args], cwd=f.root,
        env=dict(f.env, **extra), capture_output=True, text=True, timeout=20)


def platform(f, tmp_path):
    # Explicitly synthetic cooperative receipts; these never attest native execution.
    code = """import json,sys;from pathlib import Path
from scripts import platform_coverage as p
head,tree,out=sys.argv[1:];out=Path(out)
native=p.native_identities();portable=['case_'+'0'*64,'case_'+'1'*64]
for lane in ('linux','windows'):
 selected=sorted(native+portable if lane=='windows' else portable)
 ledger=dict(schema='meta.platform.ledger.v1',sha=head,tree=tree,source_files_sha256='c'*64,source_bound=True,platform=lane,suite='main',identities=sorted(native+portable),native_identities=native,selected=selected,deferred=sorted(set(native+portable)-set(selected)))
 d=out/lane;p.write_receipt(d,dict(schema='meta.platform.receipt.v1',ledger=ledger,run_id='123',attempt='1',passed=selected,skipped=[],source_authenticity='NOT_EVALUATED',physical='NOT_RUN'))
sys.argv=['platform','aggregate','--linux',str(out/'linux'),'--windows',str(out/'windows'),'--suite','main']
raise SystemExit(p.main())"""
    return run(f, '-c', code, f.head, f.tree, str(tmp_path), GITHUB_ACTIONS='true',
               GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1')


@pytest.mark.parametrize('namespace', ['refs/replace', 'refs/agent7-replacements'])
@pytest.mark.parametrize('kind', ['clean', 'blob', 'tree', 'commit'])
def test_ci_evidence_resolves_raw_objects(tmp_path, monkeypatch, namespace, kind):
    f = fixture(tmp_path, monkeypatch, namespace, kind)
    recorded = run(f, 'scripts/record_ci_source.py', GITHUB_EVENT_NAME='push', GITHUB_SHA=f.head)
    assert recorded.returncode == 0, recorded.stderr
    assert json.loads((f.root / 'source-sha.json').read_bytes())['tree_sha'] == f.tree
    manifest_path = tmp_path / 'identities.json'
    code = "from types import SimpleNamespace;from scripts.integration_synthetic_boundary import pytest_collection_finish;pytest_collection_finish(SimpleNamespace(items=[SimpleNamespace(nodeid='tests/test_inert.py::test_inert',name='test_inert')]))"
    collected = run(f, '-c', code, META_ANALYSE_SYNTHETIC_IDENTITIES=str(manifest_path))
    assert collected.returncode == 0, collected.stderr
    manifest = json.loads(manifest_path.read_bytes())
    assert (manifest['sha'], manifest['tree']) == (f.head, f.tree)
    xml = tmp_path / 'tests.xml'
    xml.write_bytes(b'<testsuite><testcase classname="tests.test_inert" name="test_inert"/></testsuite>')
    checked = run(f, 'scripts/check_final_integration_junit.py', str(xml), str(manifest_path))
    assert checked.returncode == 0, checked.stderr
    result = platform(f, tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[0])['source_authenticity'] == 'NOT_EVALUATED'


@pytest.mark.parametrize('namespace', ['refs/replace', 'refs/agent7-replacements'])
def test_platform_still_rejects_real_tracked_change(tmp_path, monkeypatch, namespace):
    f = fixture(tmp_path, monkeypatch, namespace, 'commit')
    (f.root / 'inert.txt').write_bytes(b'actual dirty checkout\n')
    assert f.git(f.root, 'status', '--porcelain')
    result = platform(f, tmp_path)
    assert result.returncode == 1
    assert result.stdout == ''
    assert 'PLATFORM_COVERAGE_REJECTED' in result.stderr
