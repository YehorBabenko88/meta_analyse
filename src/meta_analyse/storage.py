"""Dedicated schema, batch-safe upserts; never touches other PostgreSQL schemas."""
from __future__ import annotations
import psycopg
from psycopg.types.json import Jsonb

SCHEMA = """
CREATE SCHEMA IF NOT EXISTS meta_analyse;
CREATE TABLE IF NOT EXISTS meta_analyse.candles (
  symbol TEXT NOT NULL, timeframe TEXT NOT NULL, start_ts TIMESTAMPTZ NOT NULL,
  open NUMERIC NOT NULL, high NUMERIC NOT NULL, low NUMERIC NOT NULL,
  close NUMERIC NOT NULL, volume NUMERIC NOT NULL, complete BOOLEAN NOT NULL DEFAULT true,
  PRIMARY KEY(symbol,timeframe,start_ts)
);
CREATE TABLE IF NOT EXISTS meta_analyse.profiles (
  symbol TEXT NOT NULL, start_ts TIMESTAMPTZ NOT NULL,
  poc NUMERIC NOT NULL, volume NUMERIC NOT NULL, buy_volume NUMERIC NOT NULL,
  sell_volume NUMERIC NOT NULL, profile JSONB NOT NULL, quality TEXT NOT NULL,
  PRIMARY KEY(symbol,start_ts)
);
CREATE TABLE IF NOT EXISTS meta_analyse.paper_fills (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  symbol TEXT NOT NULL, side TEXT NOT NULL, entry NUMERIC NOT NULL, exit NUMERIC NOT NULL,
  reason TEXT NOT NULL, gross NUMERIC NOT NULL, fees NUMERIC NOT NULL, net NUMERIC NOT NULL,
  exit_ts TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS meta_analyse.level_map (
  connection_id INTEGER NOT NULL, symbol TEXT NOT NULL, signature TEXT NOT NULL,
  metascalp_id BIGINT NOT NULL, PRIMARY KEY(connection_id,symbol,signature)
);
CREATE TABLE IF NOT EXISTS meta_analyse.checkpoints (
  stream TEXT PRIMARY KEY, cursor_value TEXT NOT NULL, updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""

def initialize_schema(store, ddl):
    # IF NOT EXISTS alone races on PostgreSQL catalogs across independent clients.
    # Transaction-scoped, shared by every Meta Analyse schema initializer.
    with store.connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (0x4D455441414E414C,))
        conn.execute(ddl)


class Store:
    def __init__(self, dsn, *, expected_cluster=None):
        self.dsn = dsn
        self.expected_cluster = expected_cluster

    def connect(self):
        if self.expected_cluster is not None:
            from .pg_authorized_connection import authorized_private_connection, validate_connection_parameters
            from psycopg.conninfo import conninfo_to_dict
            validate_connection_parameters(conninfo_to_dict(self.dsn), self.expected_cluster)
            return authorized_private_connection(
                lambda: psycopg.connect(self.dsn, connect_timeout=5,
                    options="-c statement_timeout=5000 -c lock_timeout=5000"), self.expected_cluster)
        return psycopg.connect(self.dsn, connect_timeout=5,
                               options="-c statement_timeout=5000 -c lock_timeout=5000")

    def initialize(self):
        initialize_schema(self, SCHEMA)

    def candle_batch(self, symbol, tf, candles, complete=True):
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.executemany("""INSERT INTO meta_analyse.candles
                    (symbol,timeframe,start_ts,open,high,low,close,volume,complete)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(symbol,timeframe,start_ts) DO UPDATE SET
                    open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                    close=EXCLUDED.close, volume=EXCLUDED.volume, complete=EXCLUDED.complete""",
                    [(symbol, tf, c.start, c.open, c.high, c.low, c.close, c.volume, complete) for c in candles])

    def profile(self, symbol, minute, quality):
        with self.connect() as conn:
            conn.execute("""INSERT INTO meta_analyse.profiles
                (symbol,start_ts,poc,volume,buy_volume,sell_volume,profile,quality)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(symbol,start_ts) DO UPDATE SET
                poc=EXCLUDED.poc,volume=EXCLUDED.volume,buy_volume=EXCLUDED.buy_volume,
                sell_volume=EXCLUDED.sell_volume,profile=EXCLUDED.profile,quality=EXCLUDED.quality""",
                (symbol, minute.start, minute.poc, minute.volume, minute.buy_volume,
                 minute.sell_volume, Jsonb({str(k): str(v) for k, v in minute.profile.items()}), quality))

    def paper_fill(self, fill):
        with self.connect() as conn:
            conn.execute("""INSERT INTO meta_analyse.paper_fills
                (symbol,side,entry,exit,reason,gross,fees,net,exit_ts) VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (fill.symbol, fill.side, fill.entry,
                fill.exit, fill.reason, fill.gross, fill.fees, fill.net, fill.exit_time))
