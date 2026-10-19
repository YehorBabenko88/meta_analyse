"""Verified Bybit historical trade import, independent from market coverage claims."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path

from .storage_migrations import initialize_archive_schema


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_rows(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"trdMatchID", "timestamp", "price", "size", "side"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("missing required trade columns")
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("duplicate trade columns")
        for row in reader:
            if None in row:
                raise ValueError("extra CSV fields")
            yield row


def parse_trade(row):
    trade_id = row.get("trdMatchID")
    if not isinstance(trade_id, str) or not trade_id.strip():
        raise ValueError("missing trade ID")
    try:
        timestamp = Decimal(row["timestamp"])
        price = Decimal(row["price"])
        quantity = Decimal(row["size"])
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise ValueError("invalid numeric trade field") from exc
    if not timestamp.is_finite() or not (0 <= timestamp < Decimal("253402300800")):
        raise ValueError("timestamp out of range")
    if not price.is_finite() or price <= 0 or not quantity.is_finite() or quantity < 0:
        raise ValueError("invalid price or quantity")
    side = row.get("side")
    if side not in ("Buy", "Sell"):
        raise ValueError("invalid trade side")
    micros = int((timestamp * 1000000).to_integral_value(rounding=ROUND_DOWN))
    try:
        time = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=micros)
    except (ValueError, OverflowError) as exc:
        raise ValueError("timestamp out of range") from exc
    return trade_id.strip(), time, price, quantity, side


def _validate_receipt(receipt):
    if receipt.get("valid") is not True or receipt.get("complete") is True:
        raise ValueError("receipt is invalid or makes unsupported completeness claim")
    if not isinstance(receipt.get("url"), str) or not receipt["url"].strip():
        raise ValueError("receipt URL is required")
    if type(receipt.get("rows")) is not int or receipt["rows"] < 0:
        raise ValueError("invalid receipt row count")
    if type(receipt.get("bytes")) is not int or receipt["bytes"] < 0:
        raise ValueError("invalid receipt byte count")
    sha = receipt.get("sha256")
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("invalid receipt sha256")


def import_verified_archive(store, path, receipt, *, venue="bybit", symbol, batch_size=5000):
    """Snapshot verified bytes; atomically commit each batch with its checkpoint.

    An advisory session lock serializes archives of the same venue/symbol.
    Committed rows count input records, not distinct trade IDs. Historical
    completeness remains unverified even after a successful import.
    """
    receipt = dict(receipt)
    _validate_receipt(receipt)
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if not isinstance(symbol, str) or not symbol.strip() or not isinstance(venue, str) or not venue.strip():
        raise ValueError("venue and symbol are required")
    path = Path(path)
    if path.stat().st_size != receipt["bytes"]:
        raise ValueError("archive byte size mismatch")
    with tempfile.TemporaryDirectory(prefix="meta-ingest-") as directory:
        snapshot = Path(directory) / ("archive.gz" if path.suffix == ".gz" else "archive.csv")
        with path.open("rb") as source, snapshot.open("wb") as target:
            remaining = receipt["bytes"]
            while remaining:
                block = source.read(min(1048576, remaining))
                if not block:
                    raise ValueError("archive shorter than receipt")
                target.write(block)
                remaining -= len(block)
            if source.read(1):
                raise ValueError("archive longer than receipt")
        digest = file_sha256(snapshot)
        if digest != receipt["sha256"]:
            raise ValueError("archive sha256 mismatch")
        count = 0
        for row in iter_rows(snapshot):
            if "symbol" in row and row["symbol"] != symbol:
                raise ValueError("archive symbol mismatch")
            parse_trade(row)
            count += 1
            if count > receipt["rows"]:
                raise ValueError("archive exceeds audited row count")
        if count != receipt["rows"] or file_sha256(snapshot) != digest:
            raise ValueError("archive rows or sha256 mismatch")
        initialize_archive_schema(store)
        with store.connect() as conn:
            conn.autocommit = True
            conn.execute("SET statement_timeout = 0")
            conn.execute("SET lock_timeout = 60000")
            key = int.from_bytes(hashlib.sha256((venue + "\0" + symbol).encode()).digest()[:8], "big", signed=True)
            conn.execute("SELECT pg_advisory_lock(%s)", (key,))
            try:
                with conn.transaction():
                    source_id, prior = conn.execute("""INSERT INTO meta_analyse.archive_sources
                        (venue,symbol,source_url,sha256,byte_size,receipt_rows,verified,verification)
                        VALUES (%s,%s,%s,%s,%s,%s,TRUE,%s::jsonb)
                        ON CONFLICT (venue,symbol,sha256) DO UPDATE SET verified=TRUE
                        RETURNING id,receipt_rows""",
                        (venue,symbol,receipt["url"],digest,receipt["bytes"],count,json.dumps(receipt))).fetchone()
                    if prior != count:
                        raise ValueError("conflicting receipt rows")
                    conn.execute("""INSERT INTO meta_analyse.archive_import_checkpoints(source_id)
                        VALUES (%s) ON CONFLICT DO NOTHING""", (source_id,))
                try:
                    checkpoint = conn.execute("""SELECT committed_rows FROM meta_analyse.archive_import_checkpoints
                        WHERE source_id=%s""", (source_id,)).fetchone()[0]
                    if checkpoint > count:
                        raise ValueError("checkpoint exceeds archive")
                    def flush(batch, end):
                        with conn.transaction():
                            with conn.cursor() as cur:
                                cur.execute("""CREATE TEMP TABLE IF NOT EXISTS archive_stage (
                                    trade_id TEXT, trade_ts TIMESTAMPTZ, price NUMERIC,
                                    quantity NUMERIC, side TEXT) ON COMMIT DELETE ROWS""")
                                with cur.copy("COPY archive_stage (trade_id,trade_ts,price,quantity,side) FROM STDIN") as copy:
                                    for trade in batch:
                                        copy.write_row(trade)
                                if cur.execute("""SELECT 1 FROM archive_stage s
                                    JOIN meta_analyse.historical_trades t ON
                                    t.venue=%s AND t.symbol=%s AND t.trade_id=s.trade_id
                                    WHERE (t.trade_ts,t.price,t.quantity,t.side) IS DISTINCT FROM
                                    (s.trade_ts,s.price,s.quantity,s.side) LIMIT 1""", (venue,symbol)).fetchone():
                                    raise ValueError("conflicting existing trade ID")
                                if cur.execute("""SELECT 1 FROM archive_stage GROUP BY trade_id
                                    HAVING count(DISTINCT (trade_ts,price,quantity,side)) > 1 LIMIT 1""").fetchone():
                                    raise ValueError("conflicting trade ID within batch")
                                cur.execute("""INSERT INTO meta_analyse.historical_trades
                                    (venue,symbol,trade_id,trade_ts,price,quantity,side,source_id)
                                    SELECT DISTINCT ON (trade_id) %s,%s,trade_id,trade_ts,price,quantity,side,%s
                                    FROM archive_stage ORDER BY trade_id
                                    ON CONFLICT (venue,symbol,trade_id) DO NOTHING""", (venue,symbol,source_id))
                                cur.execute("""UPDATE meta_analyse.archive_import_checkpoints
                                    SET committed_rows=%s,status=%s,updated_at=now()
                                    WHERE source_id=%s""", (end,"imported" if end == count else "running",source_id))
                    batch = []
                    position = 0
                    for row in iter_rows(snapshot):
                        position += 1
                        if position <= checkpoint:
                            continue
                        batch.append(parse_trade(row))
                        if len(batch) >= batch_size:
                            flush(batch, position)
                            batch.clear()
                    if batch:
                        flush(batch, position)
                    elif checkpoint == count:
                        with conn.transaction():
                            conn.execute("""UPDATE meta_analyse.archive_import_checkpoints
                                SET status='imported',updated_at=now() WHERE source_id=%s""", (source_id,))
                    return {"source_id":source_id,"rows":count,"resumed_from":checkpoint}
                except BaseException:
                    # Preserve the original import/DB failure even if marking
                    # the checkpoint failed encounters another DB error.
                    try:
                        with conn.transaction():
                            conn.execute("""UPDATE meta_analyse.archive_import_checkpoints
                                SET status='failed',updated_at=now() WHERE source_id=%s""", (source_id,))
                    except Exception:
                        pass
                    raise
            finally:
                original_error = sys.exc_info()[0] is not None
                try:
                    conn.execute("SELECT pg_advisory_unlock(%s)", (key,))
                except BaseException:
                    if not original_error:
                        raise
                    # Preserve the import/DB exception over unlock cleanup.
