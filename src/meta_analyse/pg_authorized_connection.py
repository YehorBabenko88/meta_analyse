"""Opt-in fail-closed connection wrapper for an already authorized private cluster.

Never constructs a connection from a production DSN. The caller supplies a
connection factory and immutable G1 receipt. Attestation precedes any DDL/DML.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from .pg_cluster_attestation import ExpectedCluster, attest_connected_cluster, AttestationRefused


@contextmanager
def authorized_private_connection(connect, expected: ExpectedCluster):
    """Only expose a connection after exact read-only attestation succeeds.

    A fresh connection is attested every time; this cannot establish physical
    PGDATA ownership or prevent server replacement after the check. Those are
    separate G0/G1 OS-level gates.
    """
    if not isinstance(expected, ExpectedCluster):
        raise AttestationRefused("INVALID_EXPECTED_CLUSTER")
    if not callable(connect):
        raise AttestationRefused("INVALID_CONNECTION_FACTORY")
    with connect() as conn:
        attest_connected_cluster(conn, expected)
        # Attestation's SET LOCAL expires at commit. Pin this owned connection's
        # session path too, and commit setup before yielding an idle connection:
        # witnesses must be able to start their own READ ONLY transaction.
        with conn.transaction():
            conn.execute("SET search_path TO pg_catalog")
        yield conn


def validate_connection_parameters(config, expected):
    """Pre-connect rejection; secrets never appear in refusal messages."""
    if not isinstance(expected, ExpectedCluster):
        raise AttestationRefused("INVALID_EXPECTED_CLUSTER")
    # libpq can inherit routing, service, startup-option and credential values.
    # The commissioning connection must depend only on the approved config.
    if any(name.upper().startswith("PG") and value for name, value in os.environ.items()):
        raise AttestationRefused("PG_ENVIRONMENT_FORBIDDEN")
    allowed={'host','hostaddr','port','dbname','user','password','connect_timeout'}
    if (type(config) is not dict or set(config)-allowed
            or config.get('host') not in ('127.0.0.1','localhost')
            or config.get('hostaddr', '127.0.0.1')!='127.0.0.1'
            or type(config.get('port')) not in (str,int)
            or str(config.get('port'))!=str(expected.port)
            or config.get('dbname')!=expected.database or config.get('user')!=expected.role):
        raise AttestationRefused("CONNECTION_PARAMETERS_MISMATCH")
