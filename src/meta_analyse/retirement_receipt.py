"""Migration-only read-only receipts for retired Meta persistent state.

Never writes, exports row contents, authenticates a market source or provisions PG.
The returned hashes are local comparison evidence, NOT a signed attestation.
"""
from __future__ import annotations

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


def persisted_state_receipt(store, table: str, *, max_rows: int = 1_000_000):
    """Bounded-memory digest of one explicitly scoped, locked-down SQL result.

    Store.connect must be authorized by the private cluster ownership contract.
    This never claims a source-complete or authoritative market snapshot.
    """
    if type(table) is not str or table not in _SQL:
        raise ValueError("UNAPPROVED_STATE_TABLE")
    if type(max_rows) is not int or not 1 <= max_rows <= 10_000_000:
        raise ValueError("INVALID_ROW_BUDGET")
    if getattr(store, "expected_cluster", None) is None:
        raise ValueError("EXPECTED_CLUSTER_REQUIRED")

    sql, width = _SQL[table]
    digest = sha256(b"meta.persisted-state.digest.v1\0" + table.encode() + b"\0")
    count = 0
    previous_key = None
    with store.connect() as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            cursor = connection.execute(sql)
            while True:
                rows = cursor.fetchmany(256)
                if not rows:
                    break
                if len(rows) > 256:
                    raise ValueError("INVALID_FETCH_BATCH")
                for row in rows:
                    if not isinstance(row, (list, tuple)) or len(row) != width:
                        raise ValueError("INVALID_STATE_ROW")
                    count += 1
                    if count > max_rows:
                        raise ValueError("STATE_ROW_BUDGET_EXCEEDED")
                    # Protect against a compromised cursor dropping ORDER BY,
                    # duplicating an identity or returning inconsistent rows.
                    key = (row[0] if table != "level_map" else tuple(row[:3]))
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
