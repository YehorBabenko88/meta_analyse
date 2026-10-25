"""Opt-in fail-closed connection wrapper for an already authorized private cluster.

Never constructs a connection from a production DSN. The caller supplies a
connection factory and immutable G1 receipt. Attestation precedes any DDL/DML.
"""
from __future__ import annotations

from contextlib import contextmanager
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
    try:
        with connect() as conn:
            attest_connected_cluster(conn, expected)
            yield conn
    except AttestationRefused:
        raise
