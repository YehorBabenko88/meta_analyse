"""Additive schema for verified historical trades; never asserts market completeness."""
from .storage import initialize_schema

ARCHIVE_SCHEMA = """
CREATE SCHEMA IF NOT EXISTS meta_analyse;
CREATE TABLE IF NOT EXISTS meta_analyse.archive_sources (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 venue TEXT NOT NULL, symbol TEXT NOT NULL, source_url TEXT NOT NULL,
 sha256 TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
 byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
 receipt_rows BIGINT NOT NULL CHECK (receipt_rows >= 0),
 verified BOOLEAN NOT NULL DEFAULT FALSE,
 coverage_verified BOOLEAN NOT NULL DEFAULT FALSE,
 verification JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE (venue, symbol, sha256)
);
CREATE TABLE IF NOT EXISTS meta_analyse.historical_trades (
 venue TEXT NOT NULL, symbol TEXT NOT NULL, trade_id TEXT NOT NULL,
 trade_ts TIMESTAMPTZ NOT NULL, price NUMERIC NOT NULL CHECK (price > 0),
 quantity NUMERIC NOT NULL CHECK (quantity >= 0),
 side TEXT NOT NULL CHECK (side IN ('Buy','Sell')),
 source_id BIGINT NOT NULL REFERENCES meta_analyse.archive_sources(id),
 PRIMARY KEY (venue, symbol, trade_id)
);
CREATE INDEX IF NOT EXISTS historical_trades_time_idx ON meta_analyse.historical_trades(venue,symbol,trade_ts DESC);
CREATE INDEX IF NOT EXISTS historical_trades_price_idx ON meta_analyse.historical_trades(venue,symbol,price,trade_ts DESC);
CREATE INDEX IF NOT EXISTS historical_trades_quantity_idx ON meta_analyse.historical_trades(venue,symbol,quantity,trade_ts DESC);
CREATE TABLE IF NOT EXISTS meta_analyse.archive_import_checkpoints (
 source_id BIGINT PRIMARY KEY REFERENCES meta_analyse.archive_sources(id),
 committed_rows BIGINT NOT NULL DEFAULT 0 CHECK (committed_rows >= 0),
 status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','failed','imported')),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS meta_analyse.archive_coverage (
 source_id BIGINT NOT NULL REFERENCES meta_analyse.archive_sources(id),
 start_ts TIMESTAMPTZ NOT NULL, end_ts TIMESTAMPTZ NOT NULL,
 independent_verification BOOLEAN NOT NULL DEFAULT FALSE,
 missing_intervals JSONB NOT NULL DEFAULT '[]'::jsonb,
 CHECK (start_ts < end_ts), PRIMARY KEY(source_id,start_ts,end_ts)
);
"""

def initialize_archive_schema(store):
    initialize_schema(store, ARCHIVE_SCHEMA)
