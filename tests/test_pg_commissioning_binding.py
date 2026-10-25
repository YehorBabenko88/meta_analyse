"""Pure fake-connection proof that commissioning callers cannot skip new attestation."""
import importlib.util
from pathlib import Path
import sys
import pytest
from meta_analyse.storage import Store
from meta_analyse.pg_cluster_attestation import AttestationRefused
from test_pg_cluster_connection import FakeConn,GOOD,POLICY

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'commissioning'))
spec=importlib.util.spec_from_file_location('private_initializer',ROOT/'commissioning/initialize-private-schema.py')
initializer=importlib.util.module_from_spec(spec);spec.loader.exec_module(initializer)


def test_initializer_missing_independent_receipt_never_connects(monkeypatch):
    monkeypatch.setattr(initializer.psycopg,'connect',lambda **k:pytest.fail('MISSING_RECEIPT_CONNECTED'))
    with pytest.raises(AttestationRefused):initializer.initialize_new_schema({}, {})


@pytest.mark.parametrize('caller',['store','initializer'])
def test_commissioning_wrong_cluster_never_reaches_ddl_dml(monkeypatch,caller):
    row=list(GOOD);row[5]='111';conn=FakeConn(row)
    monkeypatch.setattr(initializer.psycopg,'connect',lambda *a,**k:conn)
    monkeypatch.setattr(initializer,'verify_database_role',lambda *a:pytest.fail('BEFORE_ATTESTATION'))
    with pytest.raises(AttestationRefused):
        if caller=='store':
            with Store('host=127.0.0.1 port=55480 dbname=meta_commission_test user=meta_commission_test',expected_cluster=POLICY).connect() as allowed:allowed.execute('CREATE TABLE synthetic(i int)')
        else:initializer.initialize_new_schema(dict(host='127.0.0.1',port='55480',dbname='meta_commission_test',user='meta_commission_test'), {}, expected_cluster=POLICY)
    assert all(not sql.startswith(('CREATE','INSERT','UPDATE','DELETE','DROP')) for sql in conn.queries)


def test_commissioning_store_attests_every_fresh_connection(monkeypatch):
    connections=[]
    def connect(*a,**k):
        conn=FakeConn(GOOD);connections.append(conn);return conn
    monkeypatch.setattr(initializer.psycopg,'connect',connect)
    store=Store('host=127.0.0.1 port=55480 dbname=meta_commission_test user=meta_commission_test',expected_cluster=POLICY)
    for _ in range(2):
        with store.connect() as conn:conn.execute('INSERT INTO synthetic VALUES (1)')
    assert len(connections)==2
    for conn in connections:
        assert conn.queries[0]=='SET TRANSACTION READ ONLY'
        assert 'pg_control_system' in conn.queries[1]
        assert conn.queries[2].startswith('INSERT')

def test_system_identifier_result_requires_exact_text():
    from meta_analyse.pg_cluster_attestation import attest_connected_cluster
    row=list(GOOD);row[5]=int(GOOD[5])
    with pytest.raises(AttestationRefused):attest_connected_cluster(FakeConn(row),POLICY)

@pytest.mark.parametrize('caller',['store','initializer'])
def test_wrong_dsn_refuses_before_any_connection(monkeypatch,caller):
    monkeypatch.setattr(initializer.psycopg,'connect',lambda *a,**k:pytest.fail('WRONG_DSN_CONNECTED'))
    with pytest.raises(AttestationRefused):
        if caller=='store':
            with Store('host=127.0.0.1 port=5432 dbname=postgres user=postgres',expected_cluster=POLICY).connect():pass
        else:initializer.initialize_new_schema(dict(host='127.0.0.1',port='5432',dbname='postgres',user='postgres'),{},POLICY)
