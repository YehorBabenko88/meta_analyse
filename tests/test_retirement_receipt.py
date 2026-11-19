"""No production credentials or database needed for migration readback proof."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from meta_analyse.retirement_receipt import persisted_state_receipt


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.index = 0

    def fetchmany(self, size):
        assert size == 256
        batch = self.rows[self.index:self.index + size]
        self.index += len(batch)
        return batch


class Connection:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []
        self.opened = False

    def __enter__(self):
        self.opened = True
        return self

    def __exit__(self, *args):
        return False

    def transaction(self):
        return self

    def execute(self, statement):
        self.statements.append(statement)
        if statement == "SET TRANSACTION READ ONLY":
            return self
        assert statement.startswith("SELECT ")
        assert "ORDER BY " in statement
        assert all(word not in statement for word in ("INSERT ", "UPDATE ", "DELETE ", "CREATE "))
        return Cursor(self.rows)


class Store:
    def __init__(self, rows):
        self.expected_cluster = object()
        self.connection = Connection(rows)
        self.connect_calls = 0

    def connect(self):
        self.connect_calls += 1
        return self.connection


def paper_row(identity, *, timestamp=None):
    timestamp = timestamp or datetime(2026, 11, 19, tzinfo=timezone.utc)
    return (identity, "BTCUSDT", "short", Decimal("102.0000"),
            Decimal("100.00"), "target", Decimal("1.23"),
            Decimal("0.10"), Decimal("1.13"), timestamp)


def test_paper_digest_is_deterministic_read_only_and_contains_no_trade_data():
    state = Store([paper_row(1), paper_row(2)])
    result = persisted_state_receipt(state, "paper_fills")
    assert result == persisted_state_receipt(Store([paper_row(1), paper_row(2)]), "paper_fills")
    assert result["row_count"] == 2
    assert len(result["sha256"]) == 64
    assert result["source_status"] == "UNVERIFIED_LOCAL_READBACK"
    assert result["execution_authority"] is False
    assert result["trading_authorized"] is False
    assert "BTCUSDT" not in repr(result)
    assert state.connection.statements[0] == "SET TRANSACTION READ ONLY"
    assert len(state.connection.statements) == 2
    assert state.connect_calls == 1

    altered = persisted_state_receipt(Store([paper_row(1), paper_row(3)]), "paper_fills")
    assert altered["sha256"] != result["sha256"]


def test_level_ids_and_checkpoints_have_independent_exact_state_digests():
    levels = Store([(1, "BTCUSDT", "source-a", 21),
                    (2, "BTCUSDT", "source-b", 22)])
    paper = persisted_state_receipt(levels, "level_map")
    assert paper["row_count"] == 2
    assert paper["table"] == "level_map"
    assert len(levels.connection.statements) == 2
    stamps = [( "levels", "cursor-1", datetime(2026, 11, 19, tzinfo=timezone.utc))]
    checkpoint = persisted_state_receipt(Store(stamps), "checkpoints")
    assert checkpoint["table"] == "checkpoints"
    assert checkpoint["sha256"] != paper["sha256"]


@pytest.mark.parametrize("table", ["missing", "", "__class__", "paper_fills;DROP TABLE X"])
def test_unauthorized_table_refused_without_connecting(table):
    state = Store([])
    with pytest.raises(ValueError, match="UNAPPROVED_STATE_TABLE"):
        persisted_state_receipt(state, table)
    assert state.connect_calls == 0


def test_missing_expected_cluster_and_invalid_budget_refused_before_sql():
    state = Store([])
    state.expected_cluster = None
    with pytest.raises(ValueError, match="EXPECTED_CLUSTER_REQUIRED"):
        persisted_state_receipt(state, "paper_fills")
    assert state.connect_calls == 0
    for value in (0, -1, True, 10_000_001):
        with pytest.raises(ValueError, match="INVALID_ROW_BUDGET"):
            persisted_state_receipt(Store([]), "paper_fills", max_rows=value)


def test_duplicate_or_unsorted_paper_identity_does_not_issue_receipt():
    for rows in ([paper_row(2), paper_row(1)],
                 [paper_row(1), paper_row(1)]):
        with pytest.raises(ValueError, match="INVALID_STATE_ORDER"):
            persisted_state_receipt(Store(rows), "paper_fills")


def test_truncated_result_and_nonfinite_value_are_rejected_not_hashed():
    with pytest.raises(ValueError, match="STATE_ROW_BUDGET_EXCEEDED"):
        persisted_state_receipt(Store([paper_row(1), paper_row(2)]), "paper_fills",
                                max_rows=1)
    broken = list(paper_row(1))
    broken[6] = Decimal("NaN")
    with pytest.raises(ValueError, match="NONFINITE_PERSISTED_VALUE"):
        persisted_state_receipt(Store([broken]), "paper_fills")


def test_timezone_offset_normalization_and_naive_refusal():
    utc = paper_row(1)
    offset = paper_row(1, timestamp=datetime(
        2026, 11, 19, 1, 0, tzinfo=timezone(timedelta(hours=1))))
    reference = paper_row(1, timestamp=datetime(2026, 11, 19, tzinfo=timezone.utc))
    assert persisted_state_receipt(Store([offset]), "paper_fills")["sha256"] == (
        persisted_state_receipt(Store([reference]), "paper_fills")["sha256"]
    )
    naive = paper_row(1, timestamp=datetime(2026, 11, 19))
    with pytest.raises(ValueError, match="NAIVE_PERSISTED_TIMESTAMP"):
        persisted_state_receipt(Store([naive]), "paper_fills")
