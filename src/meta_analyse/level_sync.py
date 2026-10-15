"""Fail-closed ownership-aware MetaScalp level reconciliation.

Only levels carrying this application's stable signature are managed. PostgreSQL
is a durable audit index, not a substitute for reading the terminal's state.
"""
from __future__ import annotations
import asyncio
import hashlib
import logging
from decimal import Decimal

LOG = logging.getLogger(__name__)
PREFIX = "meta_analyse:"

def signature(symbol, level):
    raw = f"{symbol}|{level.timeframe}|{level.kind}|{level.source_start.isoformat()}|{level.price}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]

def owned_id(row):
    if not isinstance(row, dict):
        return None
    note = str(row.get("note") or row.get("Note") or "")
    if not note.startswith(PREFIX):
        return None
    value = row.get("id", row.get("Id"))
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def parse_rows(response):
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        for key in ("items", "list", "levels", "data"):
            if isinstance(response.get(key), list):
                return response[key]
    raise ValueError("Unknown MetaScalp levels response; refusing destructive synchronization")

class LevelSync:
    def __init__(self, terminal):
        self.terminal = terminal
        self._locks = {}

    async def replace(self, connection, symbol, report, *, connection_verified=False,
                      instrument_verified=False):
        from .level_publish import publication_decision
        decision = publication_decision(report, connection_verified=connection_verified,
                                        instrument_verified=instrument_verified)
        if not decision.allowed:
            raise ValueError(decision.reason)
        lock = self._locks.setdefault((connection, symbol), asyncio.Lock())
        async with lock:
            rows = parse_rows(await self.terminal.levels(connection, symbol))
            existing = {}
            for row in rows:
                ident = owned_id(row)
                if ident is not None:
                    note = str(row.get("note") or row.get("Note"))
                    existing[note] = ident
            wanted = {PREFIX + signature(symbol, level): level for level in report.levels}
            # First remove stale app-owned lines, never arbitrary terminal lines.
            for note, ident in existing.items():
                if note not in wanted:
                    await self.terminal.remove_level(connection, ident)
            # On uncertain POST outcome, fail and re-read terminal before retrying.
            for note, level in wanted.items():
                if note in existing:
                    continue
                rule = "GreaterThanEqual" if level.kind == "high" else "LessThanEqual"
                await self.terminal.add_level(connection, symbol, str(level.price), rule, note)
            return len(wanted)

    async def crossed(self, connection, symbol, previous: Decimal, current: Decimal):
        """Delete only owned levels crossed between two *observed* prices."""
        lock = self._locks.setdefault((connection, symbol), asyncio.Lock())
        async with lock:
            rows = parse_rows(await self.terminal.levels(connection, symbol))
            deleted = 0
            for row in rows:
                ident = owned_id(row)
                if ident is None:
                    continue
                try:
                    price = Decimal(str(row.get("price", row.get("Price"))))
                except (TypeError, ValueError):
                    raise ValueError("Unknown level price; refusing to guess")
                if min(previous, current) <= price <= max(previous, current):
                    await self.terminal.remove_level(connection, ident)
                    deleted += 1
            return deleted
