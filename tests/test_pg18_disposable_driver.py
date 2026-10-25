"""Fake Docker/SQL only; never provision a server."""
import json
from types import SimpleNamespace
import pytest
from scripts import run_pg18_disposable_ci as d

CID = 'a' * 64


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(d.sys, 'platform', 'linux')
    for key in list(d.os.environ):
        if key.upper().startswith('PG'): monkeypatch.delenv(key)
    for key, value in dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
                           META_ANALYSE_DISPOSABLE_PG18='1', GITHUB_RUN_ID='123',
                           GITHUB_RUN_ATTEMPT='1', GITHUB_SHA='c'*40,
                           META_ANALYSE_TEST_SOURCE_SHA='b'*40).items():
        monkeypatch.setenv(key, value)
    calls = []; labels = {}; sql = []
    def run(args, **kwargs):
        calls.append(args)
        out = ''
        if args[:2] == ['docker', 'create']:
            labels.update(x.split('=', 1) for i, x in enumerate(args) if i and args[i-1] == '--label')
            out = CID
        if args[:2] == ['docker', 'inspect']:
            out = json.dumps([dict(Id=CID, Config=dict(Labels=dict(labels)))])
        if 'pg_controldata' in args: out = 'Database system identifier: 123456\n'
        return SimpleNamespace(returncode=0, stdout=out, stderr='PRIVATE')
    class Conn:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, query):
            sql.append(query)
            return SimpleNamespace(fetchone=lambda: ('180001','127.0.0.1',55480,'disposable_admin','postgres','123456'))
    monkeypatch.setattr(d.subprocess, 'run', run)
    monkeypatch.setattr(d, 'connect', lambda **kw: Conn())
    return calls, labels, sql, Conn


@pytest.mark.parametrize('key,value', [('RUNNER_ENVIRONMENT','self-hosted'),
    ('GITHUB_ACTIONS','false'),('META_ANALYSE_DISPOSABLE_PG18','0'),
    ('GITHUB_RUN_ID','0'),('GITHUB_RUN_ATTEMPT','bad'),
    ('META_ANALYSE_TEST_SOURCE_SHA','bad'),('META_ANALYSE_TEST_SOURCE_SHA',''),('PGHOST','foreign')])
def test_unapproved_environment_runs_no_command(setup, monkeypatch, tmp_path, key, value):
    monkeypatch.setenv(key, value)
    assert d.run(tmp_path/'out.xml', tmp_path/'private.log') == 1
    assert setup[0] == []


def test_success_is_loopback_tmpfs_and_cleans_owned_container(setup, tmp_path):
    assert d.run(tmp_path/'out.xml', tmp_path/'private.log') == 0
    calls, _, sql, _ = setup
    assert setup[1]['meta-analyse.sha'] == 'b'*40  # Exact checkout, not PR event merge SHA.
    create = calls[0]
    assert '--tmpfs' in create and '--network=host' in create
    for limit in ('--memory=768m','--cpus=1','--pids-limit=128','--shm-size=128m',
                  '/var/lib/postgresql:rw,size=512m,noexec,nosuid,nodev'):
        assert limit in create
    assert not any('5432' in arg or '--volume' in arg for arg in create)
    assert 'listen_addresses=127.0.0.1' in create and 'port=55480' in create
    assert calls[-1] == ['docker','rm','--force',CID]
    assert sql[0].startswith('SELECT') and sql[1].startswith('REVOKE')
    assert json.loads((tmp_path/'out.postgres.json').read_text()) == {'server_version':180001}


def test_existing_version_receipt_blocks_before_commands(setup, tmp_path):
    receipt = tmp_path/'out.postgres.json'
    receipt.write_bytes(b'STALE_PRIVATE')
    assert d.run(tmp_path/'out.xml', tmp_path/'private.log') == 1
    assert setup[0] == [] and receipt.read_bytes() == b'STALE_PRIVATE'


def test_image_labels_remain_owned_and_bootstrap_has_timeouts(setup, monkeypatch, tmp_path):
    original = d.subprocess.run
    def image(args, **kwargs):
        result = original(args, **kwargs)
        if args[:2] == ['docker','inspect']:
            info = json.loads(result.stdout)
            info[0]['Config']['Labels']['org.opencontainers.image.title'] = 'PostgreSQL'
            result.stdout = json.dumps(info)
        return result
    configs = []
    def connect(**kwargs):
        configs.append(kwargs)
        return setup[3]()
    monkeypatch.setattr(d.subprocess, 'run', image)
    monkeypatch.setattr(d, 'connect', connect)
    assert d.run(tmp_path/'out.xml', tmp_path/'private.log') == 0
    assert setup[0][-1] == ['docker','rm','--force',CID]
    assert configs[0]['connect_timeout'] == 5
    assert configs[0]['options'] == '-c statement_timeout=5000 -c lock_timeout=5000'


def test_foreign_labels_are_never_removed(setup, monkeypatch, tmp_path):
    original = d.subprocess.run
    def foreign(args, **kwargs):
        result = original(args, **kwargs)
        if args[:2] == ['docker','inspect']:
            result.stdout = json.dumps([dict(Id=CID, Config=dict(Labels={}))])
        return result
    monkeypatch.setattr(d.subprocess, 'run', foreign)
    assert d.run(tmp_path/'out.xml', tmp_path/'private.log') == 1
    assert not any(c[:2] == ['docker','rm'] for c in setup[0])


def test_wrong_sql_system_id_prevents_revoke_and_still_cleans(setup, monkeypatch, tmp_path):
    class Wrong(setup[3]):
        def execute(self, query):
            setup[2].append(query)
            return SimpleNamespace(fetchone=lambda: ('180001','127.0.0.1',55480,'disposable_admin','postgres','999'))
    monkeypatch.setattr(d, 'connect', lambda **kw: Wrong())
    assert d.run(tmp_path/'out.xml', tmp_path/'private.log') == 1
    assert len(setup[2]) == 1
    assert setup[0][-1] == ['docker','rm','--force',CID]


@pytest.mark.parametrize('stage', ['start','pytest'])
def test_start_failure_cleans_without_sql_or_private_output(setup, monkeypatch, tmp_path, capsys, stage):
    original = d.subprocess.run
    def failed(args, **kwargs):
        result = original(args, **kwargs)
        if (stage == 'start' and args[:2] == ['docker','start']) or (stage == 'pytest' and args[0] == d.sys.executable): result.returncode = 1
        return result
    monkeypatch.setattr(d.subprocess, 'run', failed)
    assert d.run(tmp_path/'out.xml', tmp_path/'private.log') == 1
    if stage == 'start': assert not setup[2]
    assert setup[0][-1] == ['docker','rm','--force',CID]
    assert 'PRIVATE' not in str(capsys.readouterr())
