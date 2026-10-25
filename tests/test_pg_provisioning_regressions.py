"""Offline regression contracts for reviewed private PG provisioning only."""
from pathlib import Path
import re
import pytest
from meta_analyse.pg_cluster_plan import ClusterPlan, PlanRefused, plan_only

ROOT = Path(__file__).resolve().parents[1]


def test_new_database_role_is_bound_and_not_silently_truncated():
    sql = (ROOT / 'commissioning/create-test-db.sql').read_text()
    assert "pg_catalog.length(:'test_role')<=63" in sql
    assert ":'test_role'=:'test_db'" in sql
    assert ":'test_role'<>'meta_commission_bootstrap'" in sql
    assert sql.index("pg_catalog.length(:'test_role')<=63") < sql.index('CREATE ROLE')


def test_provisioner_never_stops_an_unattested_process_or_uses_shared_log():
    source = (ROOT / 'commissioning/prepare-private-cluster.ps1').read_text()
    assert not re.search(r'pg_ctl.exe.*\bstop\b', source)
    assert "(Join-Path $data 'postgresql.log')" in source
    assert '$SessionName.Length -gt 63' in source


@pytest.mark.parametrize('component', ['bad*name', 'bad?name', 'bad|name', 'bad<name', 'bad>name', 'bad"name', 'bad\x01name'])
def test_plan_rejects_non_filesystem_windows_components(component):
    local = r'C:\Users\Synthetic\AppData\Local'
    with pytest.raises(PlanRefused):
        plan_only(ClusterPlan(local + '\\MetaAnalyseCommissioning\\' + component,
                  'meta_commission_test', 'meta_commission_test'), localappdata=local)


def test_plan_refuses_network_pgdata_even_when_localappdata_is_network():
    local = r'\\server\share\Local'
    with pytest.raises(PlanRefused):
        plan_only(ClusterPlan(local + r'\MetaAnalyseCommissioning\new',
                  'meta_commission_test', 'meta_commission_test'), localappdata=local)

def test_initializer_repins_catalog_after_identity_transaction(monkeypatch):
    from test_pg_commissioning_binding import initializer
    from test_pg_cluster_connection import FakeConn, GOOD, POLICY
    conn = FakeConn(GOOD)
    monkeypatch.setattr(initializer.psycopg, 'connect', lambda **kw: conn)
    def before_role(*args):
        assert conn.queries[3] == 'SET search_path TO pg_catalog'
        assert conn.queries[4] == 'SET LOCAL search_path TO pg_catalog'
        raise ValueError('guard verified')
    monkeypatch.setattr(initializer, 'verify_database_role', before_role)
    with pytest.raises(ValueError, match='guard verified'):
        initializer.initialize_new_schema(dict(host='127.0.0.1', port='55480',
            dbname=POLICY.database, user=POLICY.role), {}, POLICY)

def test_enrollment_binding_cannot_be_disabled_by_python_optimization(tmp_path):
    import subprocess
    import sys
    source = (ROOT / 'commissioning/prepare-private-cluster.ps1').read_text()
    check = source.split("$check=@'", 1)[1].split("'@", 1)[0]
    (tmp_path / 'host_identity.py').write_text("def load_private(_):\n    return {'database': {'data_directory': r'C:\\approved\\pgdata', 'port': 55480, 'dbname': 'meta_commission_test', 'user': 'meta_commission_test'}}\n")
    import os
    environment = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    result = subprocess.run([sys.executable, '-O', '-c', check, str(tmp_path), 'synthetic',
        r'C:\Users\Synthetic\AppData\Local\MetaAnalyseCommissioning\unapproved',
        'meta_commission_test', r'C:\Users\Synthetic\AppData\Local'], capture_output=True, env=environment)
    assert result.returncode != 0, 'optimized interpreter bypassed encrypted PGDATA binding'
    assert b'ENCRYPTED_DATABASE_BINDING_MISMATCH' in result.stderr

@pytest.mark.parametrize('caller', ['initializer', 'preflight'])
def test_operator_pg_connections_have_fixed_connection_statement_and_lock_bounds(monkeypatch, caller):
    from test_pg_commissioning_binding import initializer
    from test_pg_cluster_connection import FakeConn, GOOD, POLICY
    import preflight
    captured = []
    def connect(**kwargs):
        captured.append(kwargs)
        return FakeConn(GOOD)
    monkeypatch.setattr(initializer.psycopg, 'connect', connect)
    module = initializer if caller == 'initializer' else preflight
    def stop_after_connection(*args):
        raise ValueError('bounded synthetic stop')
    monkeypatch.setattr(module, 'verify_database_role', stop_after_connection)
    config = dict(host='127.0.0.1', port='55480', dbname=POLICY.database,
                  user=POLICY.role, connect_timeout=9999)
    with pytest.raises(ValueError, match='bounded synthetic stop'):
        if caller == 'initializer':
            module.initialize_new_schema(config, {}, POLICY)
        else:
            module.inspect_database(config, {}, POLICY.system_identifier)
    assert captured[0]['connect_timeout'] == 5
    assert captured[0]['options'] == '-c statement_timeout=5000 -c lock_timeout=5000'
    assert config['connect_timeout'] == 9999

def test_bootstrap_requires_external_file_control_identity_before_create():
    source = (ROOT / 'commissioning/create-test-db.sql').read_text()
    before_create = source[:source.index('CREATE ROLE')]
    assert r'\if :{?expected_system_identifier}' in before_create
    assert "SET search_path TO pg_catalog;" in before_create
    assert "(pg_catalog.pg_control_system()).system_identifier::pg_catalog.text=:'expected_system_identifier'" in before_create
    assert ":'expected_system_identifier' ~ '^[1-9][0-9]{0,19}$'" in before_create
    for name in ('current_database', 'current_setting', 'pg_database'):
        assert not re.search(rf'(?<![\w.]){name}\b', before_create)


def test_bootstrap_file_control_receipt_is_captured_before_start_and_passed_to_sql():
    source = (ROOT / 'commissioning/prepare-private-cluster.ps1').read_text()
    assert source.index('pg_controldata.exe') < source.index('pg_ctl.exe')
    assert source.index('initdb.exe') < source.index('pg_controldata.exe')
    assert 'expected_system_identifier=$expectedSystemIdentifier' in source
    assert "$env:LC_ALL='C'" in source and 'finally { $env:LC_ALL=$previousLocale }' in source
    assert '$systemIdLines.Count -ne 1' in source

def test_authorized_connection_pins_session_catalog_and_yields_idle_after_setup():
    from contextlib import contextmanager
    from test_pg_cluster_connection import FakeConn, GOOD, POLICY
    from meta_analyse.pg_authorized_connection import authorized_private_connection
    class Transactional(FakeConn):
        path = 'public,pg_catalog'
        in_transaction = False
        read_only = False
        @contextmanager
        def transaction(self):
            assert not self.in_transaction, 'wrapper left transaction open before witness'
            self.in_transaction = True
            previous_path = self.path
            self.local_path = False
            try:
                yield self
            finally:
                if self.local_path:
                    self.path = previous_path
                self.read_only = False
                self.in_transaction = False
        def execute(self, statement):
            if statement == 'SET LOCAL search_path TO pg_catalog':
                self.path = 'pg_catalog'
                self.local_path = True
            if statement == 'SET search_path TO pg_catalog':
                self.path = 'pg_catalog'
            if statement == 'SET TRANSACTION READ ONLY':
                assert self.in_transaction
                self.read_only = True
            return super().execute(statement)
    conn = Transactional(GOOD)
    with authorized_private_connection(lambda: conn, POLICY) as allowed:
        assert allowed.path == 'pg_catalog', 'attestation SET LOCAL expired before caller SQL'
        assert not allowed.in_transaction and not allowed.read_only
        # A later witness must still be able to open a fresh read-only transaction.
        with allowed.transaction():
            allowed.execute('SET TRANSACTION READ ONLY')
            assert allowed.read_only
    assert conn.queries[3] == 'SET search_path TO pg_catalog'


def test_disposable_fixture_refuses_production_port_under_optimized_python():
    import subprocess,sys,json
    code=r'''
import importlib.util,sys,os,json
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'src'))
import psycopg
for name in tuple(os.environ):
    if name.upper().startswith('PG'):os.environ.pop(name)
seen=[]
def connect(**kwargs):
    seen.append(True);raise RuntimeError('NO_REAL_CONNECTION')
psycopg.connect=connect
os.environ.update(META_ANALYSE_TEST_SYSTEM_ID='123456',META_ANALYSE_TEST_ADMIN_DSN='host=127.0.0.1 port=5432 dbname=postgres user=disposable_admin')
spec=importlib.util.spec_from_file_location('disposable_test',root/'tests/test_pg18_disposable_acceptance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
try:next(m.private_database.__wrapped__())
except Exception:pass
print(json.dumps({'connected':bool(seen)}))
'''
    result=subprocess.run([sys.executable,'-O','-B','-c',code,str(ROOT)],capture_output=True,text=True)
    assert result.returncode==0 and json.loads(result.stdout)=={'connected':False}

def test_bootstrap_pgdata_comparison_handles_accepted_trailing_separator_only():
    # Planner accepts this spelling; PostgreSQL canonicalize_path removes its
    # trailing separator before exporting DataDir through the GUC.
    local = r'C:\Users\Synthetic\AppData\Local'
    candidate = local + '\\MetaAnalyseCommissioning\\new\\'
    plan_only(ClusterPlan(candidate, 'meta_commission_test', 'meta_commission_test'), localappdata=local)
    sql = (ROOT / 'commissioning/create-test-db.sql').read_text()
    guard = "pg_catalog.rtrim(pg_catalog.replace(pg_catalog.current_setting('data_directory'),pg_catalog.chr(92),'/'),'/')=pg_catalog.rtrim(pg_catalog.replace(:'expected_data_directory',pg_catalog.chr(92),'/'),'/')"
    assert guard in sql[:sql.index('CREATE ROLE')]
    assert 'pg_catalog.lower(' not in sql and 'pg_catalog.upper(' not in sql
    assert "(pg_catalog.pg_control_system()).system_identifier::pg_catalog.text=:'expected_system_identifier'" in sql[:sql.index('CREATE ROLE')]
