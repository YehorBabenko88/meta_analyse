"""Explicit hosted disposable PostgreSQL 18.1 acceptance, never a target-PC probe.

Excluded from synthetic suites. The isolated job must independently obtain
META_ANALYSE_TEST_SYSTEM_ID from its own pg_controldata before invoking pytest,
and revoke PUBLIC CONNECT on postgres/template1 in that fresh container.
"""
import importlib.util
import os
from pathlib import Path
import sys
import uuid

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus
from psycopg.conninfo import conninfo_to_dict
import pytest

from meta_analyse.pg_authorized_connection import authorized_private_connection
from meta_analyse.pg_cluster_attestation import ExpectedCluster, AttestationRefused, attest_connected_cluster
from meta_analyse.pg_checkpoint_witness import capture_witness, verify_witness

ENABLED = (os.environ.get('META_ANALYSE_DISPOSABLE_PG18') == '1'
           and os.environ.get('GITHUB_ACTIONS') == 'true' and sys.platform == 'linux'
           and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted')
pytestmark = pytest.mark.skipif(not ENABLED, reason='explicit hosted Linux disposable PG18 gate required')


def require(condition):
    if not condition:raise RuntimeError('DISPOSABLE_PG18_IDENTITY_REFUSED')


def _bootstrap_identity(conn, identifier):
    row = conn.execute("""SELECT pg_catalog.current_setting('server_version_num'),
        pg_catalog.host(pg_catalog.inet_server_addr()), pg_catalog.inet_server_port(),
        current_user, pg_catalog.current_database(),
        (pg_catalog.pg_control_system()).system_identifier::pg_catalog.text""").fetchone()
    require(row == ('180001', '127.0.0.1', 55480, 'disposable_admin', 'postgres', identifier))


@pytest.fixture(scope='module')
def private_database():
    # Fail, do not skip, when an explicitly enabled job lacks its independent receipt.
    identifier = os.environ['META_ANALYSE_TEST_SYSTEM_ID']
    require(identifier.isascii() and identifier.isdecimal() and not identifier.startswith('0'))
    require(not any(k.upper().startswith('PG') and v for k, v in os.environ.items()))
    admin_config = conninfo_to_dict(os.environ['META_ANALYSE_TEST_ADMIN_DSN'])
    require(set(admin_config) <= {'host', 'hostaddr', 'port', 'dbname', 'user', 'password', 'connect_timeout'})
    require(admin_config['host'] == '127.0.0.1' and admin_config.get('hostaddr', '127.0.0.1') == '127.0.0.1')
    require(admin_config['port'] == '55480' and admin_config['dbname'] == 'postgres')
    require(admin_config['user'] == 'disposable_admin')
    name = 'meta_commission_' + uuid.uuid4().hex
    password = uuid.uuid4().hex
    expected = ExpectedCluster(identifier, name, name)
    created_role = created_db = False
    with psycopg.connect(**admin_config, autocommit=True) as admin:
        _bootstrap_identity(admin, identifier)  # No DDL precedes the external receipt match.
        try:
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(name), sql.Literal(password)))
            created_role = True
            admin.execute(sql.SQL('CREATE DATABASE {} OWNER {} TEMPLATE template0').format(sql.Identifier(name), sql.Identifier(name)))
            created_db = True
            admin.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(name)))
            other_connects=admin.execute("""SELECT count(*) FROM pg_catalog.pg_database WHERE datallowconn
                AND datname<>%s AND pg_catalog.has_database_privilege(%s,oid,'CONNECT')""", (name, name)).fetchone()[0]
            require(other_connects == 0)
            config = dict(host='127.0.0.1', port=55480, dbname=name, user=name, password=password, connect_timeout=5)
            yield config, expected
        finally:
            # Never FORCE/drop an unknown database, stop servers, or clean filesystem paths.
            _bootstrap_identity(admin, identifier)
            if created_db:
                require(admin.execute('SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_catalog.pg_database WHERE datname=%s', (name,)).fetchone() == (name,))
                admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
            if created_role:
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(name)))


def test_default_control_permissions_and_normal_attestation(private_database):
    config, expected = private_database
    with psycopg.connect(**config) as conn:
        privileges = conn.execute("""SELECT
            pg_catalog.has_function_privilege(current_user,'pg_catalog.pg_control_system()','EXECUTE'),
            pg_catalog.has_function_privilege(current_user,'pg_catalog.pg_control_checkpoint()','EXECUTE')""").fetchone()
        assert privileges == (True, True)  # PG REL_18_1 source has no PUBLIC revocation.
        conn.rollback()
        attest_connected_cluster(conn, expected)
        assert conn.execute('SHOW transaction_read_only').fetchone() == ('off',)
    with authorized_private_connection(lambda: psycopg.connect(**config), expected) as conn:
        assert conn.info.transaction_status == TransactionStatus.IDLE
        assert conn.execute('SHOW search_path').fetchone() == ('pg_catalog',)
        conn.commit()
        assert conn.execute('SHOW search_path').fetchone() == ('pg_catalog',)


def test_initializer_and_read_only_witness_are_viable(private_database):
    config, expected = private_database
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'commissioning'))
    spec = importlib.util.spec_from_file_location('disposable_initializer', root / 'commissioning/initialize-private-schema.py')
    initializer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(initializer)
    initializer.initialize_new_schema(config, {'database': {'dbname': expected.database, 'user': expected.role}}, expected)
    with authorized_private_connection(lambda: psycopg.connect(**config), expected) as conn:
        conn.execute('CREATE TABLE meta_analyse.orderbook_observations (symbol text, update_id bigint, sequence bigint)')
        conn.execute("INSERT INTO meta_analyse.orderbook_observations VALUES ('BTCUSDT',1,2)")
    result = capture_witness(lambda: psycopg.connect(**config), expected, 'BTCUSDT', 1, 2)
    assert result.status == 'PENDING' and result.ticket is not None
    assert verify_witness(lambda: psycopg.connect(**config), expected, result.ticket).status in ('PENDING', 'OBSERVED')


def test_wrong_receipt_and_database_refuse_before_ddl(private_database):
    config, expected = private_database
    for wrong in (ExpectedCluster(str(int(expected.system_identifier) + 1), expected.database, expected.role),
                  ExpectedCluster(expected.system_identifier, 'meta_commission_wrong', 'meta_commission_wrong')):
        with pytest.raises(AttestationRefused):
            with authorized_private_connection(lambda: psycopg.connect(**config), wrong) as conn:
                conn.execute('CREATE TABLE public.receipt_bypass (i int)')
    with psycopg.connect(**config) as conn:
        assert conn.execute("SELECT pg_catalog.to_regclass('public.receipt_bypass')").fetchone() == (None,)
    # Avoid supplying the dedicated password to another role; bootstrap identity was
    # independently verified by the fixture and cannot satisfy a dedicated receipt.
    admin_config = conninfo_to_dict(os.environ['META_ANALYSE_TEST_ADMIN_DSN'])
    with pytest.raises(AttestationRefused):
        with authorized_private_connection(lambda: psycopg.connect(**admin_config), expected):
            pytest.fail('bootstrap role/database was exposed as dedicated connection')


def test_read_only_and_failed_ddl_transactions_rollback(private_database):
    config, expected = private_database
    with authorized_private_connection(lambda: psycopg.connect(**config), expected) as conn:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            with conn.transaction():
                conn.execute('SET TRANSACTION READ ONLY')
                conn.execute('CREATE TABLE public.readonly_bypass (i int)')
        with pytest.raises(ValueError, match='synthetic rollback'):
            with conn.transaction():
                conn.execute('CREATE TABLE public.rollback_probe (i int)')
                raise ValueError('synthetic rollback')
        assert conn.execute("SELECT pg_catalog.to_regclass('public.readonly_bypass'), pg_catalog.to_regclass('public.rollback_probe')").fetchone() == (None, None)
