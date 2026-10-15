"""Crash-recoverable orchestration: journal intent, reconcile, then verify terminal."""
from __future__ import annotations
import asyncio
import hashlib
from .level_sync import LevelSync, PREFIX, signature, parse_rows, owned_id

def generation_for(symbol, report):
    notes=sorted(PREFIX+signature(symbol,level) for level in report.levels)
    return hashlib.sha256("\n".join(notes).encode()).hexdigest()

class DurableLevelSync:
    def __init__(self,terminal,journal):
        self.terminal=terminal
        self.journal=journal
        self.sync=LevelSync(terminal)
        self.locks={}

    async def replace(self,connection,symbol,report,*,connection_verified=False,instrument_verified=False):
        from .level_publish import publication_decision
        decision=publication_decision(report,connection_verified=connection_verified,
                                       instrument_verified=instrument_verified)
        if not decision.allowed:
            raise ValueError(decision.reason)
        lock=self.locks.setdefault((connection,symbol),asyncio.Lock())
        async with lock:
            generation=generation_for(symbol,report)
            await asyncio.to_thread(self.journal.mark,connection,symbol,generation,"pending")
            try:
                await self.sync.replace(connection,symbol,report,
                    connection_verified=True,instrument_verified=True)
                rows=parse_rows(await self.terminal.levels(connection,symbol))
                actual={str(row.get("note") or row.get("Note")) for row in rows
                        if owned_id(row) is not None}
                expected={PREFIX+signature(symbol,level) for level in report.levels}
                if actual!=expected:
                    raise RuntimeError("terminal level set differs after reconciliation")
            except Exception as exc:
                await asyncio.to_thread(self.journal.mark,connection,symbol,generation,
                                        "failed",type(exc).__name__)
                raise
            await asyncio.to_thread(self.journal.mark,connection,symbol,generation,"verified")
            return len(expected)
