"""Receipts and historical paper-fill transfer for retired Meta state.

The Meta source is read only. Terminan owns archive writes and verified readback.
The returned hashes are local comparison evidence, not a signed attestation.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json


_SQL = {
    "paper_fills": (
        "SELECT id,symbol,side,entry,exit,reason,gross,fees,net,exit_ts "
        "FROM meta_analyse.paper_fills ORDER BY id",
        10,
    ),
    "level_map": (
        "SELECT connection_id,symbol,signature,metascalp_id "
        "FROM meta_analyse.level_map ORDER BY connection_id,symbol,signature",
        4,
    ),
    "checkpoints": (
        "SELECT stream,cursor_value,updated_at "
        "FROM meta_analyse.checkpoints ORDER BY stream",
        3,
    ),
}


def _canonical(value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("INVALID_ROW_VALUE")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("NONFINITE_PERSISTED_VALUE")
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("NAIVE_PERSISTED_TIMESTAMP")
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds")
    if type(value) in (int, str):
        return value
    raise ValueError("UNSUPPORTED_PERSISTED_TYPE")


def _check_source(store, max_rows, limit):
    if type(max_rows) is not int or not 1 <= max_rows <= limit:
        raise ValueError("INVALID_ROW_BUDGET")
    if getattr(store, "expected_cluster", None) is None:
        raise ValueError("EXPECTED_CLUSTER_REQUIRED")


def _encoded_rows(cursor, table, max_rows):
    _, width = _SQL[table]
    count = 0
    previous_key = None
    while rows := cursor.fetchmany(256):
        if len(rows) > 256:
            raise ValueError("INVALID_FETCH_BATCH")
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) != width:
                raise ValueError("INVALID_STATE_ROW")
            count += 1
            if count > max_rows:
                raise ValueError("STATE_ROW_BUDGET_EXCEEDED")
            key = row[0] if table != "level_map" else tuple(row[:3])
            if previous_key is not None:
                try:
                    in_order = key > previous_key
                except TypeError as exc:
                    raise ValueError("INVALID_STATE_ORDER") from exc
                if not in_order:
                    raise ValueError("INVALID_STATE_ORDER")
            previous_key = key
            encoded = json.dumps(
                [_canonical(value) for value in row],
                ensure_ascii=True, allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(encoded) > 262_144:
                raise ValueError("STATE_ROW_TOO_LARGE")
            yield encoded


def _receipt(table, rows):
    digest = sha256(b"meta.persisted-state.digest.v1\0" + table.encode() + b"\0")
    count = 0
    for count, encoded in enumerate(rows, 1):
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return {
        "schema": "meta.persisted-state.digest.v1",
        "table": table,
        "row_count": count,
        "sha256": digest.hexdigest(),
        "source_status": "UNVERIFIED_LOCAL_READBACK",
        "execution_authority": False,
        "trading_authorized": False,
    }


def persisted_state_receipt(store, table: str, *, max_rows: int = 1_000_000):
    """Digest one explicitly scoped SQL result from an authorized cluster."""
    if type(table) is not str or table not in _SQL:
        raise ValueError("UNAPPROVED_STATE_TABLE")
    _check_source(store, max_rows, 10_000_000)
    sql, _ = _SQL[table]
    with store.connect() as connection, connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        return _receipt(table, _encoded_rows(connection.execute(sql), table, max_rows))


def archive_paper_fills(store, terminan_ledger, source_id: str, *, max_rows: int = 1_000_000):
    """Send one authorized historical snapshot to the existing Terminan archive.

    Use a stable source ID to retry the same snapshot. Terminan rejects a
    previously committed ID with a different digest. No source rows are logged
    or staged on disk by Meta.
    """
    _check_source(store, max_rows, 1_000_000)
    table = "paper_fills"
    sql, _ = _SQL[table]
    with store.connect() as connection, connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        with connection.cursor(name="meta_archive_receipt") as cursor:
            cursor.execute(sql)
            receipt = _receipt(table, _encoded_rows(cursor, table, max_rows))
        with connection.cursor(name="meta_archive_delivery") as cursor:
            cursor.execute(sql)
            with closing(json.loads(row) for row in _encoded_rows(cursor, table, max_rows)) as rows:
                return terminan_ledger.import_meta_fills(source_id, rows, receipt)
