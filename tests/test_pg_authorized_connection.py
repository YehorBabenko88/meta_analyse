"""Offline connection gate tests; no network, PostgreSQL or ADMINIT."""
import pytest
from meta_analyse.pg_authorized_connection import authorized_private_connection
from meta_analyse.pg_cluster_attestation import ExpectedCluster, AttestationRefused


class FakeResult:
    def __init__(self, row):
        self.row = row
    def fetchone(self):
        return self.row


class FakeConn:
    def __init__(self, row):
        self.row = row
        self.queries = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def transaction(self):
        return self
    def execute(self, sql):
        self.queries.append(sql)
        return FakeResult(self.row)


POLICY = ExpectedCluster("12345678901234567890", "meta_commission_test",
                         "meta_commission_test")
GOOD = ("meta_commission_test", "meta_commission_test", 180001,
        "127.0.0.1", 55480, "12345678901234567890", True)


def test_successful_attestation_precedes_any_write():
    conn = FakeConn(GOOD)
    with authorized_private_connection(lambda: conn, POLICY) as allowed:
        allowed.execute("INSERT INTO synthetic VALUES (1)")
    assert conn.queries[0] == "SET TRANSACTION READ ONLY"
    assert "pg_control_system()" in conn.queries[1]
    assert conn.queries[2].startswith("INSERT")


@pytest.mark.parametrize("index,value", [
    (0, "postgres"), (1, "postgres"), (2, 180006),
    (3, "0.0.0.0"), (4, 5432), (5, "111"), (6, False),
])
def test_wrong_identity_refuses_before_mutation(index, value):
    row = list(GOOD)
    row[index] = value
    conn = FakeConn(tuple(row))
    with pytest.raises(AttestationRefused):
        with authorized_private_connection(lambda: conn, POLICY) as allowed:
            allowed.execute("DROP TABLE synthetic")
    assert not any(q.startswith("DROP") for q in conn.queries)


def test_invalid_expected_cluster_refuses_before_connect():
    called = []
    with pytest.raises(AttestationRefused):
        with authorized_private_connection(lambda: called.append(True), None):
            pass
    assert not called


def test_unicode_digit_identifier_refused():
    with pytest.raises(AttestationRefused):
        ExpectedCluster("１２３", "meta_commission_test", "meta_commission_test")


def test_connection_factory_failure_does_not_authorize():
    def unavailable():
        raise OSError("disposable server not running")
    with pytest.raises(OSError, match="disposable server"):
        with authorized_private_connection(unavailable, POLICY):
            pytest.fail("connection must not be yielded")


def test_attestation_failure_closes_connection_context():
    conn = FakeConn(("postgres", *GOOD[1:]))
    exited = []
    original_exit = conn.__exit__
    def record_exit(*args):
        exited.append(True)
        return original_exit(*args)
    conn.__exit__ = record_exit
    # Python special-method lookup uses the class, so use a wrapper below.
    class Tracked(FakeConn):
        def __exit__(self, *args):
            exited.append(True)
            return False
    tracked = Tracked(("postgres", *GOOD[1:]))
    with pytest.raises(AttestationRefused):
        with authorized_private_connection(lambda: tracked, POLICY):
            pytest.fail("wrong cluster must not be yielded")
    assert exited == [True]
