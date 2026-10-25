"""Fail-closed, read-only G0 PostgreSQL 18.1 connection identity attestation.

No connection is opened here. A caller must supply an already connected
read-only/transactional psycopg connection. No DDL, DML or privilege changes.
"""
from __future__ import annotations

from dataclasses import dataclass


class AttestationRefused(ValueError):
    """Fixed public refusal code; never include DSN, paths or credentials."""


@dataclass(frozen=True)
class ExpectedCluster:
    system_identifier: str
    database: str
    role: str
    port: int = 55480
    version_num: int = 180001

    def __post_init__(self):
        if (not isinstance(self.system_identifier, str)
                or not self.system_identifier.isascii()
                or not self.system_identifier.isdecimal()
                or not 1 <= len(self.system_identifier) <= 20
                or self.system_identifier.startswith("0")
                or int(self.system_identifier) > 18446744073709551615
                or not isinstance(self.database, str)
                or not self.database.startswith("meta_commission_")
                or not len("meta_commission_") < len(self.database) <= 63
                or self.database == "meta_commission_bootstrap"
                or not all(c.isascii() and (c.islower() or c.isdigit() or c == "_") for c in self.database)
                or not isinstance(self.role, str)
                or self.role != self.database
                or type(self.port) is not int or self.port != 55480
                or type(self.version_num) is not int or self.version_num != 180001):
            raise AttestationRefused("INVALID_EXPECTED_CLUSTER")


def attest_connected_cluster(conn, expected: ExpectedCluster) -> None:
    """Inspect the connected server; fail closed before any caller writes.

    Requires a role with permission to read pg_control_system(). On denial,
    refuse rather than weakening system-identifier proof.
    """
    if not isinstance(expected, ExpectedCluster):
        raise AttestationRefused("INVALID_EXPECTED_CLUSTER")
    try:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            row = conn.execute(
                """SELECT current_database(), current_user,
                          current_setting('server_version_num')::integer,
                          inet_server_addr()::text, inet_server_port(),
                          (pg_control_system()).system_identifier::text,
                          (SELECT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb
                                  AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls
                                  AND session_user=current_user
                                  AND current_user=(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database())
                                  AND NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user))
                                  AND NOT EXISTS(SELECT 1 FROM pg_database WHERE datallowconn AND datname<>current_database() AND has_database_privilege(current_user,oid,'CONNECT'))
                             FROM pg_roles WHERE rolname=current_user)"""
            ).fetchone()
    except Exception:
        raise AttestationRefused("CLUSTER_ATTESTATION_UNAVAILABLE") from None
    if (not isinstance(row, (tuple, list)) or len(row) != 7 or
            row[0] != expected.database or row[1] != expected.role or
            type(row[2]) is not int or row[2] != expected.version_num or
            row[3] != "127.0.0.1" or type(row[4]) is not int or
            row[4] != expected.port or type(row[5]) is not str or row[5] != expected.system_identifier or
            row[6] is not True):
        raise AttestationRefused("CLUSTER_IDENTITY_MISMATCH")
