"""Offline source contract audit for PR47 commissioning entrypoints.

No database, host, subprocess or filesystem mutation. This is not a runtime
PostgreSQL compatibility test.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_commissioning_schema_requires_attestation_before_ddl():
    text = source("commissioning/initialize-private-schema.py")
    assert "validate_connection_parameters(config, expected_cluster)" in text
    assert "with authorized_private_connection(" in text
    assert text.index("with authorized_private_connection(") < text.index("conn.execute(SCHEMA)")
    assert "pg_catalog.pg_advisory_xact_lock" in text


def test_preflight_uses_authorized_private_connection():
    text = source("commissioning/preflight.py")
    assert "validate_connection_parameters(config,expected)" in text
    assert "with authorized_private_connection(" in text
    assert text.index("with authorized_private_connection(") < text.index("verify_database_role(conn,policy)")


def test_cluster_setup_refuses_5432_and_existing_pgdata():
    text = source("commissioning/prepare-private-cluster.ps1")
    assert "55480" in text
    assert "Test-Path -LiteralPath $data" in text
    assert "ReparsePoint" in text
    assert "PostgreSQL\\) 18\\.1" in text
    assert "OperatorApproved" in text


def test_witness_is_read_only_and_never_calls_checkpoint():
    text = source("src/meta_analyse/pg_checkpoint_witness.py")
    assert 'conn.execute("SET TRANSACTION READ ONLY")' in text
    assert "pg_catalog.pg_control_checkpoint()" in text
    assert 'conn.execute("CHECKPOINT")' not in text


def test_expected_cluster_not_implicitly_from_dsn():
    text = source("src/meta_analyse/pg_cluster_attestation.py")
    assert "system_identifier: str" in text
    assert "pg_catalog.pg_control_system()" in text
    assert "CLUSTER_IDENTITY_MISMATCH" in text
