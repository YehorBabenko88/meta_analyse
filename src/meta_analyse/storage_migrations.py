"""Additive PostgreSQL schema for historical archive ingestion."""
from .storage import initialize_schema

ARCHIVE_SCHEMA = """
CREATE SCHEMA IF NOT EXISTS meta_analyse;
CREATE TABLE IF NOT EXISTS meta_analyse.archive_sources (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 venue TEXT NOT NULL, symbol TEXT NOT NULL, source_url TEXT NOT NULL,
 sha256 TEXT NOT NULL, byte_size BIGINT NOT NULL, receipt_rows BIGINT NOT NULL,
 verified BOOLEAN NOT NULL DEFAULT false,
 coverage_verified BOOLEAN NOT NULL DEFAULT false,
 verification JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE (venue,symbol,sha256)
);
CREATE TABLE IF NOT EXISTS meta_analyse.historical_trades (
 venue TEXT NOT NULL, symbol TEXT NOT NULL, trade_id TEXT NOT NULL,
 trade_ts TIMESTAMPTZ NOT NULL, price NUMERIC NOT NULL,
 quantity NUMERIC NOT NULL, side TEXT NOT NULL,
 source_id BIGINT NOT NULL REFERENCES meta_analyse.archive_sources(id),
 PRIMARY KEY (venue,symbol,trade_id)
);
CREATE INDEX IF NOT EXISTS historical_trades_time_idx ON meta_analyse.historical_trades(venue,symbol,trade_ts);
CREATE INDEX IF NOT EXISTS historical_trades_price_idx ON meta_analyse.historical_trades(venue,symbol,price);
CREATE INDEX IF NOT EXISTS historical_trades_quantity_idx ON meta_analyse.historical_trades(venue,symbol,quantity);
CREATE TABLE IF NOT EXISTS meta_analyse.archive_import_checkpoints (
 source_id BIGINT PRIMARY KEY REFERENCES meta_analyse.archive_sources(id),
 committed_rows BIGINT NOT NULL DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'pending',
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS meta_analyse.archive_coverage (
 source_id BIGINT PRIMARY KEY REFERENCES meta_analyse.archive_sources(id),
 start_ts TIMESTAMPTZ, end_ts TIMESTAMPTZ,
 independent_verification JSONB,
 missing_intervals JSONB
);
"""

def initialize_archive_schema(store):
    initialize_schema(store, ARCHIVE_SCHEMA)
