"""Read-only SQL observations, never a physical durability certificate.

Uses caller-supplied authorized connection factories. No CHECKPOINT, writes,
grants, connection creation, polling, or automatic escalation. Tickets are
in-process observations, not authenticated G1 receipts. The expected cluster
must come independently from the caller's approved receipt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re

from .pg_authorized_connection import authorized_private_connection
from .pg_cluster_attestation import ExpectedCluster


@dataclass(frozen=True, repr=False)
class WitnessTicket:
    expected: ExpectedCluster
    symbol: str
    update_id: int
    sequence: int
    marker: str
    timeline: int
    captured_at: datetime

    def __repr__(self):
        return "WitnessTicket(<private observation>)"


@dataclass(frozen=True)
class WitnessResult:
    status: str
    ticket: WitnessTicket | None = field(default=None, repr=False)


_QUERY = """SELECT EXISTS(
    SELECT 1 FROM meta_analyse.orderbook_observations
    WHERE symbol=%s AND update_id=%s AND sequence=%s),
    pg_catalog.pg_current_wal_insert_lsn()::pg_catalog.text, pg_catalog.pg_current_wal_flush_lsn()::pg_catalog.text,
    checkpoint_lsn::pg_catalog.text, redo_lsn::pg_catalog.text, timeline_id
    FROM pg_catalog.pg_control_checkpoint()"""


def _lsn(value):
    if type(value) is not str or not re.fullmatch(r"(?:0|[1-9A-F][0-9A-F]{0,7})/(?:0|[1-9A-F][0-9A-F]{0,7})", value):
        raise ValueError("BLOCKED")
    high, low = value.split("/")
    return (int(high, 16) << 32) | int(low, 16)


def _identity(symbol, update_id, sequence):
    return (type(symbol) is str and re.fullmatch(r"[A-Z0-9]{1,40}", symbol) is not None
            and type(update_id) is int and 0 <= update_id < 2**63
            and type(sequence) is int and 0 <= sequence < 2**63)


def _clock(now):
    value = datetime.now(timezone.utc) if now is None else now
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("BLOCKED")
    return value


def _observe(connect, expected, symbol, update_id, sequence):
    with authorized_private_connection(connect, expected) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL search_path TO pg_catalog")
            row = conn.execute(_QUERY, (symbol, update_id, sequence)).fetchone()
    if (type(row) not in (tuple, list) or len(row) != 6
            or row[0] is not True or type(row[5]) is not int
            or not 1 <= row[5] <= 2**32-1):
        raise ValueError("BLOCKED")
    marker, flush, checkpoint, redo = (_lsn(value) for value in row[1:5])
    if redo > checkpoint:
        raise ValueError("BLOCKED")
    return row, (marker, flush, checkpoint, redo)


def capture_witness(connect, expected, symbol, update_id, sequence, *, now=None):
    """Capture a visible committed identity and WAL marker; return PENDING.

    This never declares checkpoint completion from the capture observation.
    Fake tests verify ordering and predicates, not PostgreSQL persistence.
    """
    try:
        captured_at = _clock(now)
        if not isinstance(expected, ExpectedCluster) or not _identity(symbol, update_id, sequence):
            raise ValueError("BLOCKED")
        row, _ = _observe(connect, expected, symbol, update_id, sequence)
        ticket = WitnessTicket(expected, symbol, update_id, sequence, row[1], row[5], captured_at)
        return WitnessResult("PENDING", ticket)
    except Exception:
        return WitnessResult("BLOCKED")


def verify_witness(connect, expected, ticket, *, now=None):
    """Observe later visibility, flush and checkpoint progress without forcing it.

    OBSERVED requires checkpoint redo LSN >= captured marker: a checkpoint
    record after the marker alone could belong to a checkpoint begun earlier.
    A timeline change is blocked; no cross-timeline ordering is inferred.
    All failures expose only a fixed status. A ticket expires after 300 seconds.
    """
    try:
        current = _clock(now)
        if (type(ticket) is not WitnessTicket or not isinstance(expected, ExpectedCluster)
                or ticket.expected != expected
                or not _identity(ticket.symbol, ticket.update_id, ticket.sequence)
                or type(ticket.timeline) is not int or not 1 <= ticket.timeline <= 2**32-1):
            raise ValueError("BLOCKED")
        age = (current - _clock(ticket.captured_at)).total_seconds()
        if not 0 <= age <= 300:
            raise ValueError("BLOCKED")
        marker = _lsn(ticket.marker)
        row, (insert, flush, checkpoint, redo) = _observe(
            connect, expected, ticket.symbol, ticket.update_id, ticket.sequence)
        if row[5] != ticket.timeline or insert < marker:
            raise ValueError("BLOCKED")
        return WitnessResult("OBSERVED" if flush >= marker and redo >= marker else "PENDING")
    except Exception:
        return WitnessResult("BLOCKED")
