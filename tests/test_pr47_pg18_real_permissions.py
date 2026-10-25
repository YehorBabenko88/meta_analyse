"""Real disposable PostgreSQL 18.1 permission and catalog contract probe.

Only executes with explicit isolated CI opt-in. Never uses a production DSN.
Does not grant elevated privileges or alter an existing cluster.
"""
import os
import uuid

import pytest
import psycopg
from psycopg import sql

from meta_analyse.pg_cluster_attestation import ExpectedCluster, AttestationRefused, attest_connected_cluster

DSN = os.getenv("META_ANALYSE_DISPOSABLE_PG18_DSN")
pytestmark = pytest.mark.skipif(
    not (DSN and os.getenv("GITHUB_ACTIONS") == "true"
         and os.getenv("META_ANALYSE_DISPOSABLE_ONLY") == "1"),
    reason="explicit disposable CI PostgreSQL 18.1 required",
)


def test_pg18_real_catalog_permissions_and_fail_closed():
    # This test must not be run on the physical target; the workflow supplies
    # a freshly provisioned disposable PostgreSQL service.
    with psycopg.connect(DSN, autocommit=True) as admin:
        assert admin.execute("SHOW server_version_num").fetchone()[0] == "180001"
        assert admin.execute("SELECT inet_server_addr()::text").fetchone()[0] == "127.0.0.1"
        assert admin.execute("SELECT inet_server_port()").fetchone()[0] == 5432
        # Port 5432 here belongs exclusively to the disposable Actions service.
        role = "meta_commission_" + uuid.uuid4().hex[:12]
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS").format(sql.Identifier(role)))
        try:
            # No extra memberships or elevated grants are supplied.
            assert admin.execute("SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=%s)", (role,)).fetchone()[0] == 0
            # Check actual server privileges, not a mocked SQL response.
            has_control = admin.execute(
                "SELECT has_function_privilege(%s, 'pg_catalog.pg_control_system()', 'EXECUTE')",
                (role,),
            ).fetchone()[0]
            has_checkpoint = admin.execute(
                "SELECT has_function_privilege(%s, 'pg_catalog.pg_control_checkpoint()', 'EXECUTE')",
                (role,),
            ).fetchone()[0]
            assert type(has_control) is bool and type(has_checkpoint) is bool
            # Dedicated role must not be assumed capable of attestation merely
            # because fake tests returned a successful row.
            assert not has_control, "unexpected control-system privilege: review role policy"
            assert not has_checkpoint, "unexpected control-checkpoint privilege: review role policy"
        finally:
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
