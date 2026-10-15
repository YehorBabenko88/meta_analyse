"""Persist orderbook observations and open interest without cross-stream timestamp invention."""
from __future__ import annotations
from datetime import datetime,timezone
from psycopg.types.json import Jsonb
from .storage import initialize_schema

DDL="""
CREATE SCHEMA IF NOT EXISTS meta_analyse;
CREATE TABLE IF NOT EXISTS meta_analyse.orderbook_observations (
 symbol TEXT NOT NULL,
 exchange_ts TIMESTAMPTZ NOT NULL,
 update_id BIGINT NOT NULL,
 sequence BIGINT NOT NULL,
 received_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 bids JSONB NOT NULL,
 asks JSONB NOT NULL,
 PRIMARY KEY(symbol,update_id,sequence)
);
CREATE INDEX IF NOT EXISTS orderbook_observations_time
 ON meta_analyse.orderbook_observations(symbol,exchange_ts);
CREATE TABLE IF NOT EXISTS meta_analyse.open_interest_samples (
 symbol TEXT NOT NULL,
 interval_name TEXT NOT NULL,
 exchange_ts TIMESTAMPTZ NOT NULL,
 open_interest NUMERIC NOT NULL CHECK (open_interest >= 0),
 received_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 PRIMARY KEY(symbol,interval_name,exchange_ts)
);
"""

class MarketStore:
    def __init__(self,store):
        self.store=store

    def initialize(self):
        initialize_schema(self.store, DDL)

    def book(self,symbol,book,exchange_ms):
        if not book.valid or not exchange_ms or book.update_id is None or book.sequence is None:
            raise ValueError("unverified book observation")
        with self.store.connect() as conn:
            conn.execute("""
                INSERT INTO meta_analyse.orderbook_observations
                (symbol,exchange_ts,update_id,sequence,bids,asks)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
            """,(symbol,datetime.fromtimestamp(exchange_ms/1000,timezone.utc),
                 book.update_id,book.sequence,
                 Jsonb([[str(p),str(q)] for p,q in book.bids.items()]),
                 Jsonb([[str(p),str(q)] for p,q in book.asks.items()])))

    def open_interest(self,point,interval):
        with self.store.connect() as conn:
            conn.execute("""
                INSERT INTO meta_analyse.open_interest_samples
                (symbol,interval_name,exchange_ts,open_interest)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT(symbol,interval_name,exchange_ts)
                DO UPDATE SET open_interest=EXCLUDED.open_interest
            """,(point.symbol,interval,datetime.fromtimestamp(point.timestamp_ms/1000,timezone.utc),
                 point.open_interest))
