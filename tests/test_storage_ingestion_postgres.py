"""Isolated PostgreSQL integration: never connect without explicit test DSN."""
import hashlib
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from meta_analyse.archive_db_import import import_verified_archive
from meta_analyse.orderflow_archive_reader import read_orderflow_trades
from meta_analyse.storage import Store

DSN = os.environ.get("META_ANALYSE_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="isolated test PostgreSQL DSN not configured")


def archive(tmp_path, symbol, trade_id, name):
    path = tmp_path / (name + ".csv")
    path.write_text("timestamp,symbol,side,size,price,trdMatchID\n"
                    f"1720000000,{symbol},Buy,2,100,{trade_id}\n", encoding="utf-8")
    receipt = {"valid":True,"complete":False,
               "url":"https://example.invalid/" + name,
               "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
               "bytes":path.stat().st_size,"rows":1}
    return path, receipt


def test_resume_and_deduplication(tmp_path):
    store = Store(DSN)
    symbol = "TEST_STORAGE_" + uuid.uuid4().hex
    path, receipt = archive(tmp_path, symbol, "trade1", "first")
    first = import_verified_archive(store,path,receipt,symbol=symbol,batch_size=1)
    second = import_verified_archive(store,path,receipt,symbol=symbol,batch_size=1)
    assert first["rows"] == second["rows"] == 1
    assert second["resumed_from"] == 1
    with store.connect() as conn:
        count = conn.execute("""SELECT count(*) FROM meta_analyse.historical_trades
            WHERE venue='bybit' AND symbol=%s""", (symbol,)).fetchone()[0]
    assert count == 1


def test_concurrent_sources_same_symbol(tmp_path):
    store = Store(DSN)
    symbol = "TEST_STORAGE_" + uuid.uuid4().hex
    a = archive(tmp_path,symbol,"trade1","first")
    b = archive(tmp_path,symbol,"trade2","second")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pair: import_verified_archive(
            store,pair[0],pair[1],symbol=symbol,batch_size=1), (a,b)))
    assert len(results) == 2
    with store.connect() as conn:
        count = conn.execute("""SELECT count(*) FROM meta_analyse.historical_trades
            WHERE venue='bybit' AND symbol=%s""", (symbol,)).fetchone()[0]
    assert count == 2


def test_conflicting_archive_rolls_back_batch_and_checkpoint(tmp_path):
    store = Store(DSN)
    symbol = "TEST_STORAGE_" + uuid.uuid4().hex
    first_path, first_receipt = archive(tmp_path, symbol, "duplicate", "initial")
    import_verified_archive(store, first_path, first_receipt, symbol=symbol, batch_size=1)
    conflicting_path = tmp_path / "conflicting.csv"
    conflicting_path.write_text(
        "timestamp,symbol,side,size,price,trdMatchID\n"
        f"1720000000,{symbol},Buy,2,999,duplicate\n", encoding="utf-8")
    conflicting_receipt = {
        "valid": True, "complete": False, "url": "https://example.invalid/conflicting",
        "sha256": hashlib.sha256(conflicting_path.read_bytes()).hexdigest(),
        "bytes": conflicting_path.stat().st_size, "rows": 1,
    }
    with pytest.raises(ValueError, match="conflicting existing trade ID"):
        import_verified_archive(
            store, conflicting_path, conflicting_receipt, symbol=symbol, batch_size=1)
    with store.connect() as conn:
        saved = conn.execute("""SELECT price FROM meta_analyse.historical_trades
            WHERE venue='bybit' AND symbol=%s AND trade_id='duplicate'""",
            (symbol,)).fetchone()[0]
        checkpoint = conn.execute("""SELECT c.committed_rows FROM
            meta_analyse.archive_import_checkpoints c
            JOIN meta_analyse.archive_sources s ON s.id=c.source_id
            WHERE s.symbol=%s AND s.sha256=%s""",
            (symbol, conflicting_receipt["sha256"])).fetchone()[0]
    assert saved == 100
    assert checkpoint == 0


def test_partial_batch_failure_keeps_previous_committed_checkpoint(tmp_path):
    store = Store(DSN)
    symbol = "TEST_STORAGE_" + uuid.uuid4().hex
    seed, seed_receipt = archive(tmp_path, symbol, "collision", "seed")
    import_verified_archive(store, seed, seed_receipt, symbol=symbol, batch_size=1)
    path = tmp_path / "partial.csv"
    path.write_text(
        "timestamp,symbol,side,size,price,trdMatchID\n"
        f"1720000001,{symbol},Buy,2,100,unique\n"
        f"1720000002,{symbol},Buy,2,999,collision\n",
        encoding="utf-8")
    receipt = {
        "valid": True, "complete": False, "url": "https://example.invalid/partial",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size, "rows": 2,
    }
    with pytest.raises(ValueError, match="conflicting existing trade ID"):
        import_verified_archive(store, path, receipt, symbol=symbol, batch_size=1)
    with store.connect() as conn:
        checkpoint = conn.execute("""SELECT c.committed_rows FROM
            meta_analyse.archive_import_checkpoints c
            JOIN meta_analyse.archive_sources s ON s.id=c.source_id
            WHERE s.symbol=%s AND s.sha256=%s""",
            (symbol, receipt["sha256"])).fetchone()[0]
        unique = conn.execute("""SELECT count(*) FROM meta_analyse.historical_trades
            WHERE venue='bybit' AND symbol=%s AND trade_id='unique'""",
            (symbol,)).fetchone()[0]
    assert checkpoint == 1
    assert unique == 1


def test_resume_after_failed_batch_and_repaired_archive_conflict(tmp_path):
    """After a failed second batch, rerun preserves the first checkpoint."""
    store = Store(DSN)
    symbol = "TEST_STORAGE_" + uuid.uuid4().hex
    seed, seed_receipt = archive(tmp_path, symbol, "collision", "resume_seed")
    import_verified_archive(store, seed, seed_receipt, symbol=symbol, batch_size=1)
    path = tmp_path / "resume_partial.csv"
    path.write_text(
        "timestamp,symbol,side,size,price,trdMatchID\n"
        f"1720000001,{symbol},Buy,2,100,unique\n"
        f"1720000002,{symbol},Buy,2,999,collision\n",
        encoding="utf-8")
    receipt = {
        "valid": True, "complete": False, "url": "https://example.invalid/resume_partial",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size, "rows": 2,
    }
    for attempt in range(2):
        with pytest.raises(ValueError, match="conflicting existing trade ID"):
            import_verified_archive(store, path, receipt, symbol=symbol, batch_size=1)
    with store.connect() as conn:
        source_id, checkpoint = conn.execute("""SELECT s.id,c.committed_rows
            FROM meta_analyse.archive_sources s
            JOIN meta_analyse.archive_import_checkpoints c ON c.source_id=s.id
            WHERE s.symbol=%s AND s.sha256=%s""",
            (symbol, receipt["sha256"])).fetchone()
        count = conn.execute("""SELECT count(*) FROM meta_analyse.historical_trades
            WHERE venue='bybit' AND symbol=%s AND trade_id='unique'""",
            (symbol,)).fetchone()[0]
    assert source_id > 0
    assert checkpoint == 1
    assert count == 1


def test_concurrent_identical_archive_is_idempotent(tmp_path):
    """Two workers racing on the same archive must not duplicate records."""
    store = Store(DSN)
    symbol = "TEST_STORAGE_" + uuid.uuid4().hex
    path, receipt = archive(tmp_path, symbol, "same_trade", "same_archive")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda _: import_verified_archive(
                store, path, receipt, symbol=symbol, batch_size=1), range(2)))
    assert sorted(item["resumed_from"] for item in results) == [0, 1]
    with store.connect() as conn:
        source_count = conn.execute("""SELECT count(*) FROM meta_analyse.archive_sources
            WHERE venue='bybit' AND symbol=%s AND sha256=%s""",
            (symbol, receipt["sha256"])).fetchone()[0]
        trade_count = conn.execute("""SELECT count(*) FROM meta_analyse.historical_trades
            WHERE venue='bybit' AND symbol=%s""", (symbol,)).fetchone()[0]
    assert source_count == 1
    assert trade_count == 1


def test_failed_import_status_preserves_committed_checkpoint(tmp_path):
    store = Store(DSN)
    symbol = "TEST_STORAGE_" + uuid.uuid4().hex
    seed, seed_receipt = archive(tmp_path, symbol, "collision", "seed_status")
    import_verified_archive(store, seed, seed_receipt, symbol=symbol, batch_size=1)
    path = tmp_path / "status_partial.csv"
    path.write_text("timestamp,symbol,side,size,price,trdMatchID\n"
                    f"1720000001,{symbol},Buy,2,100,unique\n"
                    f"1720000002,{symbol},Buy,2,999,collision\n")
    receipt = {"valid": True, "complete": False, "url": "https://example.invalid/status",
               "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "bytes": path.stat().st_size, "rows": 2}
    with pytest.raises(ValueError, match="conflicting existing trade ID"):
        import_verified_archive(store, path, receipt, symbol=symbol, batch_size=1)
    with store.connect() as conn:
        checkpoint, status = conn.execute("""SELECT c.committed_rows,c.status
            FROM meta_analyse.archive_import_checkpoints c
            JOIN meta_analyse.archive_sources s ON s.id=c.source_id
            WHERE s.symbol=%s AND s.sha256=%s""",
            (symbol, receipt["sha256"])).fetchone()
    assert (checkpoint, status) == (1, "failed")


def test_orderflow_reader_returns_exact_aliases(tmp_path):
    from decimal import Decimal
    store = Store(DSN)
    symbol = "TEST_STORAGE_" + uuid.uuid4().hex
    path, receipt = archive(tmp_path, symbol, "trade_reader", "reader")
    import_verified_archive(store, path, receipt, symbol=symbol)
    rows = read_orderflow_trades(store, venue="bybit", symbol=symbol,
                                 start_ms=1720000000000, end_ms=1720000001000)
    assert len(rows) == 1
    assert rows[0]["timestamp_ms"] == 1720000000000
    assert rows[0]["volume"] == Decimal("2")
    assert rows[0]["price"] == Decimal("100")
    assert rows[0]["side"] == "Buy"


def test_unlock_failure_does_not_mask_original_import_error(tmp_path):
    """R6: an advisory-unlock failure must not replace a trade conflict."""
    store = Store(DSN)
    symbol = "TEST_STORAGE_" + uuid.uuid4().hex
    seed, seed_receipt = archive(tmp_path, symbol, "collision", "unlock_seed")
    import_verified_archive(store, seed, seed_receipt, symbol=symbol, batch_size=1)
    path = tmp_path / "unlock_conflict.csv"
    path.write_text(
        "timestamp,symbol,side,size,price,trdMatchID\n"
        f"1720000000,{symbol},Buy,2,999,collision\n", encoding="utf-8")
    receipt = {"valid": True, "complete": False,
               "url": "https://example.invalid/unlock_conflict",
               "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "bytes": path.stat().st_size, "rows": 1}

    class UnlockFailureConnection:
        def __init__(self, underlying):
            self.underlying = underlying

        def __enter__(self):
            self.underlying.__enter__()
            return self

        def __exit__(self, *args):
            return self.underlying.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self.underlying, name)

        def execute(self, sql, params=None):
            if "pg_advisory_unlock" in sql:
                raise RuntimeError("simulated advisory unlock failure")
            return self.underlying.execute(sql, params)

    class UnlockFailureStore:
        def connect(self):
            return UnlockFailureConnection(store.connect())

    with pytest.raises(ValueError, match="conflicting existing trade ID"):
        import_verified_archive(
            UnlockFailureStore(), path, receipt, symbol=symbol, batch_size=1)
    with store.connect() as conn:
        checkpoint, status = conn.execute("""SELECT c.committed_rows,c.status
            FROM meta_analyse.archive_import_checkpoints c
            JOIN meta_analyse.archive_sources s ON s.id=c.source_id
            WHERE s.symbol=%s AND s.sha256=%s""",
            (symbol, receipt["sha256"])).fetchone()
    assert (checkpoint, status) == (0, "failed")
