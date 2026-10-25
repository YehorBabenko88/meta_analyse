"""Offline SQL resolution and libpq-environment boundary regressions.

These capture SQL sent to fakes; they do not run PostgreSQL name resolution.
"""
import re
import pytest
from meta_analyse.pg_cluster_attestation import attest_connected_cluster, AttestationRefused
from meta_analyse.pg_checkpoint_witness import _QUERY
from meta_analyse.pg_authorized_connection import validate_connection_parameters
from meta_analyse.storage import Store
from test_pg_cluster_connection import FakeConn, GOOD, POLICY


CONFIG = dict(host="127.0.0.1", port="55480", dbname="meta_commission_test", user="meta_commission_test")


def test_identity_sql_does_not_resolve_system_names_through_caller_search_path():
    conn = FakeConn(GOOD)
    attest_connected_cluster(conn, POLICY)
    sql = conn.queries[2]
    names = ("current_database", "current_setting", "inet_server_addr", "inet_server_port",
             "pg_control_system", "pg_get_userbyid", "has_database_privilege",
             "pg_database", "pg_auth_members", "pg_roles")
    for name in names:
        assert f"pg_catalog.{name}" in sql
        assert not re.search(rf"(?<![\w.]){name}\b", sql)


def test_checkpoint_sql_does_not_resolve_control_functions_through_caller_search_path():
    for name in ("pg_current_wal_insert_lsn", "pg_current_wal_flush_lsn", "pg_control_checkpoint"):
        assert f"pg_catalog.{name}(" in _QUERY
        assert not re.search(rf"(?<![\w.]){name}\b", _QUERY)


@pytest.mark.parametrize("name,value", [("PGOPTIONS", "-c search_path=public,pg_catalog"),
    ("PGHOSTADDR", "192.0.2.1"), ("PGPASSWORD", "private-fixture-value"),
    ("PGSERVICE", "untrusted"), ("pgoptions", "-c search_path=public,pg_catalog")])
def test_libpq_environment_refuses_before_optin_store_connect(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    monkeypatch.setattr("meta_analyse.storage.psycopg.connect", lambda *a, **kw: pytest.fail("UNTRUSTED_ENV_CONNECTED"))
    with pytest.raises(AttestationRefused, match="^PG_ENVIRONMENT_FORBIDDEN$"):
        with Store("host=127.0.0.1 port=55480 dbname=meta_commission_test user=meta_commission_test",
                   expected_cluster=POLICY).connect():
            pytest.fail("UNTRUSTED_ENV_EXPOSED_CONNECTION")


def test_empty_libpq_environment_does_not_refuse_config(monkeypatch):
    import os
    for name in tuple(os.environ):
        if name.upper().startswith("PG"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("PGOPTIONS", "")
    validate_connection_parameters(CONFIG, POLICY)


def test_attestation_and_witness_use_catalog_qualified_output_casts():
    conn = FakeConn(GOOD)
    attest_connected_cluster(conn, POLICY)
    assert "::pg_catalog.int4" in conn.queries[2]
    for sql in (conn.queries[2], _QUERY):
        assert not re.search(r"::\s*(text|integer)\b", sql)
        assert "::pg_catalog.text" in sql


def test_each_identity_and_witness_read_pins_catalog_search_path_before_query():
    from test_pg_checkpoint_witness import Fake, capture
    identity = FakeConn(GOOD)
    attest_connected_cluster(identity, POLICY)
    assert identity.queries[:2] == ["SET TRANSACTION READ ONLY", "SET LOCAL search_path TO pg_catalog"]
    assert "pg_control_system()" in identity.queries[2]
    observation = Fake()
    assert capture(observation).status == "PENDING"
    statements = [sql for sql, _ in observation.statements]
    assert statements[:2] == ["SET TRANSACTION READ ONLY", "SET LOCAL search_path TO pg_catalog"]
    assert "pg_control_system()" in statements[2]
    assert statements[3] == "SET search_path TO pg_catalog"
    assert statements[4:6] == ["SET TRANSACTION READ ONLY", "SET LOCAL search_path TO pg_catalog"]
    assert "pg_control_checkpoint()" in statements[6]


def test_ipv4_host_projection_does_not_refuse_documented_inet_text_netmask():
    # PostgreSQL18 text(inet) includes /32; host(inet) intentionally omits it.
    # Model only that documented projection; actual SQL remains a hosted gate.
    from test_pg_cluster_connection import FakeResult
    class InetConnection(FakeConn):
        def execute(self,query):
            self.queries.append(query)
            row=list(GOOD)
            if 'pg_control_system()' in query and 'pg_catalog.host(pg_catalog.inet_server_addr())' not in query:
                row[3]='127.0.0.1/32'
            return FakeResult(row)
    attest_connected_cluster(InetConnection(GOOD),POLICY)


@pytest.mark.parametrize('path',['src/meta_analyse/pg_cluster_attestation.py','scripts/run_pg18_disposable_ci.py','tests/test_pg18_disposable_acceptance.py'])
def test_all_server_identity_paths_project_ip_without_cidr_suffix(path):
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    text=(root/path).read_text(encoding='utf-8-sig')
    assert 'pg_catalog.host(pg_catalog.inet_server_addr())' in text
    assert 'inet_server_addr()::pg_catalog.text' not in text
