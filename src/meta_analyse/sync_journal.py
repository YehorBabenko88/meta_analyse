"""PostgreSQL reconciliation journal; independent of user-created terminal levels."""
from __future__ import annotations
from dataclasses import dataclass

DDL = """
CREATE SCHEMA IF NOT EXISTS meta_analyse;
CREATE TABLE IF NOT EXISTS meta_analyse.level_sync_journal (
    connection_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    generation TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('pending','verified','failed')),
    detail TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(connection_id,symbol)
);
"""

@dataclass(frozen=True)
class SyncRecord:
    connection_id: int
    symbol: str
    generation: str
    state: str
    detail: str

class SyncJournal:
    def __init__(self,store):
        self.store=store

    def initialize(self):
        with self.store.connect() as conn:
            conn.execute(DDL)

    def mark(self,connection_id,symbol,generation,state,detail=""):
        if state not in ("pending","verified","failed"):
            raise ValueError("invalid journal state")
        with self.store.connect() as conn:
            conn.execute("""
                INSERT INTO meta_analyse.level_sync_journal
                (connection_id,symbol,generation,state,detail)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT(connection_id,symbol) DO UPDATE SET
                generation=EXCLUDED.generation,state=EXCLUDED.state,
                detail=EXCLUDED.detail,updated_at=NOW()
            """,(connection_id,symbol,generation,state,detail))

    def get(self,connection_id,symbol):
        with self.store.connect() as conn:
            row=conn.execute("""
                SELECT generation,state,detail FROM meta_analyse.level_sync_journal
                WHERE connection_id=%s AND symbol=%s
            """,(connection_id,symbol)).fetchone()
        return SyncRecord(connection_id,symbol,*row) if row else None
