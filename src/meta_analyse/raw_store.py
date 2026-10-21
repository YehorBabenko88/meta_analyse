"""Append-only executions with idempotent conflict handling and quality flags."""
from __future__ import annotations
from psycopg.types.json import Jsonb
from .storage import initialize_schema

DDL = """
CREATE SCHEMA IF NOT EXISTS meta_analyse;
CREATE TABLE IF NOT EXISTS meta_analyse.executions (
 symbol TEXT NOT NULL,
 execution_id TEXT NOT NULL,
 exchange_ts TIMESTAMPTZ NOT NULL,
 received_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 price NUMERIC NOT NULL CHECK (price > 0),
 quantity NUMERIC NOT NULL CHECK (quantity > 0),
 taker_side TEXT NOT NULL CHECK (taker_side IN ('Buy','Sell')),
 PRIMARY KEY(symbol,execution_id)
);
CREATE INDEX IF NOT EXISTS executions_symbol_time
 ON meta_analyse.executions(symbol,exchange_ts);
CREATE TABLE IF NOT EXISTS meta_analyse.data_gaps (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 symbol TEXT NOT NULL,
 detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 reason TEXT NOT NULL,
 resolved BOOLEAN NOT NULL DEFAULT false
);
"""

class RawStore:
    def __init__(self, store):
        self.store = store

    def initialize(self):
        initialize_schema(self.store, DDL)

    def save(self, execution) -> bool:
        from datetime import datetime, timezone
        with self.store.connect() as conn:
            row = conn.execute("""
                INSERT INTO meta_analyse.executions
                (symbol,execution_id,exchange_ts,price,quantity,taker_side)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT(symbol,execution_id) DO NOTHING RETURNING execution_id
            """, (execution.symbol,execution.execution_id,
                  datetime.fromtimestamp(execution.timestamp_ms / 1000,timezone.utc),
                  execution.price,execution.quantity,execution.taker_side)).fetchone()
            return row is not None

    def gap(self, symbols, reason):
        with self.store.connect() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO meta_analyse.data_gaps(symbol,reason) VALUES (%s,%s)",
                    [(symbol,reason[:1000]) for symbol in symbols])
