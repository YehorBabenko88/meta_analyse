"""No production credentials or database needed for migration readback proof."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from meta_analyse.retirement_receipt import archive_paper_fills, persisted_state_receipt


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


@pytest.mark.parametrize("second_id", [1, 2])
def test_archive_uses_named_cursors_and_checks_second_scan(tmp_path, second_id):
    from contextlib import closing, contextmanager
    import sqlite3
    from terminan.paper_ledger import PaperReplayLedger

    state = Store([])
    scans = iter(([paper_row(1)], [paper_row(second_id)]))
    names = []

    @contextmanager
    def cursor(*, name):
        names.append(name)
        assert state.connection.statements == ["SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"]
        result = Cursor(next(scans))
        result.execute = lambda sql: assert_paper_select(sql)
        yield result

    def assert_paper_select(sql):
        assert sql.startswith("SELECT id,")
        assert sql.endswith("FROM meta_analyse.paper_fills ORDER BY id")

    state.connection.cursor = cursor
    state.connection.execute = state.connection.statements.append
    path = tmp_path / "terminan.sqlite"
    ledger = PaperReplayLedger(path)

    if second_id == 1:
        receipt = archive_paper_fills(state, ledger, "snapshot")
        assert receipt == persisted_state_receipt(Store([paper_row(1)]), "paper_fills")
        assert list(ledger.restore_meta_fills("snapshot"))[0][3:5] == ["102.0000", "100.00"]
    else:
        with pytest.raises(ValueError, match="receipt|digest"):
            archive_paper_fills(state, ledger, "snapshot")
        with closing(sqlite3.connect(path)) as connection:
            assert connection.execute(
                "SELECT name FROM sqlite_schema WHERE name = 'meta_fill_archives'"
            ).fetchone() is None
    assert len(names) == 2
    assert all(names)
    assert state.connect_calls == 1


def test_disposable_pg_archive_keeps_snapshot_across_concurrent_source_update(postgres_store, tmp_path):
    from types import SimpleNamespace
    from terminan.paper_ledger import PaperReplayLedger

    postgres_store.initialize()
    timestamp = datetime(2026, 11, 19, 12, 0, 0, 123456, tzinfo=timezone.utc)
    with postgres_store.connect() as connection:
        connection.execute(
            "INSERT INTO meta_analyse.paper_fills "
            "(symbol,side,entry,exit,reason,gross,fees,net,exit_ts) "
            "VALUES ('BTCUSDT','short',102.0000,100.00,'target',1.23,0.10,1.13,%s)",
            (timestamp,),
        )
    source = SimpleNamespace(expected_cluster=object(), connect=postgres_store.connect)
    expected = persisted_state_receipt(source, "paper_fills")
    ledger = PaperReplayLedger(tmp_path / "terminan.sqlite")

    class ConcurrentUpdate:
        def import_meta_fills(self, source_id, rows, receipt):
            assert receipt == expected
            with postgres_store.connect() as writer:
                writer.execute("UPDATE meta_analyse.paper_fills SET reason='concurrent-fixture'")
            return ledger.import_meta_fills(source_id, rows, receipt)

    assert archive_paper_fills(source, ConcurrentUpdate(), "snapshot") == expected
    restored = PaperReplayLedger(tmp_path / "terminan.sqlite")
    assert list(restored.restore_meta_fills("snapshot")) == [[
        1, "BTCUSDT", "short", "102.0000", "100.00", "target", "1.23", "0.10", "1.13",
        "2026-11-19T12:00:00.123456+00:00",
    ]]
    assert persisted_state_receipt(source, "paper_fills")["sha256"] != expected["sha256"]
