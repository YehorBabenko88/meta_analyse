"""Deterministic fail-closed fault injection for PostgreSQL attestation.

No socket, process, database, or ADMINIT access.
"""
import pytest

from meta_analyse.pg_cluster_attestation import ExpectedCluster, AttestationRefused
from meta_analyse.pg_authorized_connection import authorized_private_connection


POLICY = ExpectedCluster("12345678901234567890", "meta_commission_test", "meta_commission_test")
GOOD = ("meta_commission_test", "meta_commission_test", 180001,
        "127.0.0.1", 55480, "12345678901234567890", True)


class FakeConnection:
    def __init__(self, row, fail_at=None):
        self.row, self.fail_at, self.queries = row, fail_at, []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        return False

    def transaction(self):
        class Transaction:
            def __enter__(self):
                return None
            def __exit__(self, *args):
                return False
        return Transaction()

    def execute(self, query):
        self.queries.append(query)
        if len(self.queries) == self.fail_at:
            raise RuntimeError("PRIVATE_FAULT")
        class Result:
            def __init__(self, row):
                self.row = row
            def fetchone(self):
                return self.row
        return Result(self.row)


@pytest.mark.parametrize("fault_at", [1, 2, 3])
def test_attestation_sql_failure_closes_without_yielding(fault_at):
    connection = FakeConnection(GOOD, fail_at=fault_at)
    with pytest.raises(AttestationRefused, match="CLUSTER_ATTESTATION_UNAVAILABLE"):
        with authorized_private_connection(lambda: connection, POLICY):
            pytest.fail("unattested connection yielded")
    assert connection.closed
    assert len(connection.queries) == fault_at
    assert not any(q.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP"))
                   for q in connection.queries)


@pytest.mark.parametrize("field,value", [
    (0, "postgres"), (1, "postgres"), (2, 180006), (3, "::1"),
    (4, 5432), (5, "999"), (6, False),
])
def test_identity_mismatch_closes_without_mutation(field, value):
    row = list(GOOD)
    row[field] = value
    connection = FakeConnection(tuple(row))
    with pytest.raises(AttestationRefused, match="CLUSTER_IDENTITY_MISMATCH"):
        with authorized_private_connection(lambda: connection, POLICY):
            pytest.fail("wrong cluster yielded")
    assert connection.closed
    assert len(connection.queries) == 3


def test_valid_connection_is_yielded_only_after_read_only_probe():
    connection = FakeConnection(GOOD)
    with authorized_private_connection(lambda: connection, POLICY) as accepted:
        assert accepted is connection
        assert connection.queries[0] == "SET TRANSACTION READ ONLY"
        assert "search_path" in connection.queries[1]
        assert "pg_control_system" in connection.queries[2]
    assert connection.closed


def test_factory_exception_never_enters_mutation_scope():
    called = []
    def broken():
        called.append("factory")
        raise ConnectionError("PRIVATE_CONNECTION")
    with pytest.raises(ConnectionError):
        with authorized_private_connection(broken, POLICY):
            pytest.fail("unconnected scope yielded")
    assert called == ["factory"]


def test_attestation_result_none_fails_closed():
    connection = FakeConnection(None)
    with pytest.raises(AttestationRefused, match="CLUSTER_IDENTITY_MISMATCH"):
        with authorized_private_connection(lambda: connection, POLICY):
            pytest.fail("empty server identity yielded")
    assert connection.closed
    assert len(connection.queries) == 3


@pytest.mark.parametrize("bad", [
    (), ("meta_commission_test",),
    ("meta_commission_test", "meta_commission_test", 180001,
     "127.0.0.1", 55480, "12345678901234567890", True, "unexpected"),
])
def test_malformed_catalog_result_fails_closed(bad):
    connection = FakeConnection(bad)
    with pytest.raises(AttestationRefused, match="CLUSTER_IDENTITY_MISMATCH"):
        with authorized_private_connection(lambda: connection, POLICY):
            pytest.fail("malformed catalog result yielded")
    assert connection.closed


@pytest.mark.parametrize("field,bad", [
    (2, True), (2, "180001"), (4, True), (4, "55480"),
    (5, 12345678901234567890), (6, 1), (6, "true"),
])
def test_catalog_type_confusion_fails_closed(field, bad):
    row = list(GOOD)
    row[field] = bad
    connection = FakeConnection(tuple(row))
    with pytest.raises(AttestationRefused, match="CLUSTER_IDENTITY_MISMATCH"):
        with authorized_private_connection(lambda: connection, POLICY):
            pytest.fail("type-confused catalog identity yielded")
    assert connection.closed
