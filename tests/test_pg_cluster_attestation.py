"""Offline G0 attestation regressions: no psycopg.connect or physical host."""
import pytest
from meta_analyse.pg_cluster_attestation import (
    AttestationRefused, ExpectedCluster, attest_connected_cluster,
)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value


class FakeConnection:
    def __init__(self, row=None, error=None):
        self.row, self.error, self.statements = row, error, []

    def transaction(self):
        connection = self

        class Transaction:
            def __enter__(self):
                return connection

            def __exit__(self, *args):
                return False

        return Transaction()

    def execute(self, sql):
        self.statements.append(sql)
        if self.error:
            raise self.error
        return FakeResult(self.row)


EXPECTED = ExpectedCluster("12345678901234567890", "meta_commission_test",
                           "meta_commission_test")
GOOD = ("meta_commission_test", "meta_commission_test", 180001,
        "127.0.0.1", 55480, "12345678901234567890", True)


def test_expected_identity_matches_read_only():
    conn = FakeConnection(GOOD)
    attest_connected_cluster(conn, EXPECTED)
    assert conn.statements[0] == "SET TRANSACTION READ ONLY"
    assert all(not x.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE",
                                                  "CREATE", "DROP", "ALTER"))
               for x in conn.statements)


@pytest.mark.parametrize("field,wrong", [
    (0, "postgres"), (1, "postgres"), (2, 180006),
    (3, "::1"), (3, "0.0.0.0"), (4, 5432), (5, "999"),
    (6, False), (6, None),
])
def test_wrong_cluster_fields_refused(field, wrong):
    row = list(GOOD)
    row[field] = wrong
    with pytest.raises(AttestationRefused, match="CLUSTER_IDENTITY_MISMATCH"):
        attest_connected_cluster(FakeConnection(tuple(row)), EXPECTED)


def test_missing_privilege_or_query_failure_fails_closed():
    with pytest.raises(AttestationRefused, match="CLUSTER_ATTESTATION_UNAVAILABLE"):
        attest_connected_cluster(FakeConnection(error=PermissionError("private DSN")), EXPECTED)


@pytest.mark.parametrize("bad", [
    {"port": 5432}, {"version_num": 180006}, {"database": "postgres"},
    {"role": "postgres"}, {"system_identifier": "not-a-number"},
])
def test_invalid_expected_cluster_refused(bad):
    args = dict(system_identifier=EXPECTED.system_identifier,
                database=EXPECTED.database, role=EXPECTED.role)
    args.update(bad)
    with pytest.raises(AttestationRefused, match="INVALID_EXPECTED_CLUSTER"):
        ExpectedCluster(**args)


@pytest.mark.parametrize("bad", [
    {"database": "meta_commission_", "role": "meta_commission_"},
    {"system_identifier": "012345"},
    {"system_identifier": "１２３４"},
])
def test_noncanonical_expected_cluster_refused(bad):
    args = dict(system_identifier=EXPECTED.system_identifier,
                database=EXPECTED.database, role=EXPECTED.role)
    args.update(bad)
    with pytest.raises(AttestationRefused, match="INVALID_EXPECTED_CLUSTER"):
        ExpectedCluster(**args)


@pytest.mark.parametrize("bad", [
    {"database": "meta_commission_bootstrap", "role": "meta_commission_bootstrap"},
    {"database": "meta_commission_" + "a" * 64, "role": "meta_commission_" + "a" * 64},
    {"system_identifier": "18446744073709551616"},
])
def test_reserved_or_unrepresentable_identity_refused(bad):
    args = dict(system_identifier=EXPECTED.system_identifier,
                database=EXPECTED.database, role=EXPECTED.role)
    args.update(bad)
    with pytest.raises(AttestationRefused, match="INVALID_EXPECTED_CLUSTER"):
        ExpectedCluster(**args)


@pytest.mark.parametrize("row", [False, 7, object(), (), ("private-value",)])
def test_malformed_server_result_has_fixed_refusal(row):
    with pytest.raises(AttestationRefused, match="^CLUSTER_IDENTITY_MISMATCH$"):
        attest_connected_cluster(FakeConnection(row), EXPECTED)
