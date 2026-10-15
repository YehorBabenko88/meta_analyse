"""Safe startup recovery for previously interrupted terminal synchronization.

No desired level set can be inferred from the journal alone. Recovery must
recompute levels from verified historical candles before modifying MetaScalp.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RecoveryDecision:
    requires_recompute: bool
    can_mutate_terminal: bool
    reason: str

def decide_recovery(record, *, history_verified: bool, connection_verified: bool,
                    instrument_verified: bool) -> RecoveryDecision:
    if record is None:
        return RecoveryDecision(True,False,"no previous sync journal")
    if record.state not in ("pending","failed","verified"):
        return RecoveryDecision(True,False,"unknown journal state")
    if not history_verified:
        return RecoveryDecision(True,False,"recompute from verified historical coverage")
    if not connection_verified or not instrument_verified:
        return RecoveryDecision(False,False,"terminal connection or instrument unverified")
    return RecoveryDecision(False,True,"reconcile terminal against freshly computed desired levels")
