"""Deliver a persisted, replayable Meta fixture to Terminan's offline journal."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from terminan.paper_journal import PaperJournal
from terminan.paper_ledger import PaperReplayLedger, canonical_json


_MAX_SOURCE_BYTES = 8 * 1024 * 1024


def deliver(source: Path, expected_sha256: str, ledger_path: Path) -> dict:
    """Retry the same file and hash after interruption, using the same ledger.

    The source file is the durable input cursor. Terminan owns all accepted
    events, checkpoint state and fills. No live source is admitted here.
    """
    with Path(source).open("rb") as stream:
        raw = stream.read(_MAX_SOURCE_BYTES + 1)
    if len(raw) > _MAX_SOURCE_BYTES:
        raise ValueError("paper source byte limit")
    digest = sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("paper source digest mismatch")
    envelope = json.loads(raw)
    if (type(envelope) is not dict
            or set(envelope) != {"schema", "source_id", "symbol", "events"}
            or envelope["schema"] != "meta.paper.source.v1"):
        raise ValueError("invalid offline paper source envelope")
    events = envelope["events"]
    if type(events) is not list or not events:
        raise ValueError("offline paper source requires events")
    for sequence, event in enumerate(events, 1):
        if (type(event) is not dict or type(event.get("sequence")) is not int
                or event["sequence"] != sequence):
            raise ValueError("offline paper source sequence must be contiguous")

    source_id, symbol = envelope["source_id"], envelope["symbol"]
    run_id = f"meta-offline-{digest}"
    journal = PaperJournal(PaperReplayLedger(ledger_path), source_id, run_id, symbol)
    previous = journal.read_checkpoint()
    if previous is not None:
        sequence = previous["checkpoint"]
        if (type(sequence) is not int or not 1 <= sequence <= len(events)
                or previous["event_sha256"] != sha256(canonical_json(events[sequence - 1])).hexdigest()):
            raise RuntimeError("Terminan checkpoint disagrees with offline source")
    submitted_fills = sha256()
    fill_count = 0
    for sequence, event in enumerate(events, 1):
        ack = journal.submit(event)
        if (ack["schema"] != "terminan.paper.event.ack.v1"
                or (ack["source_id"], ack["run_id"], ack["symbol"]) != (source_id, run_id, symbol)
                or ack["checkpoint"] != sequence
                or ack["event_sha256"] != sha256(canonical_json(event)).hexdigest()
                or ack["execution_authority"] is not False or ack["trading_authorized"] is not False):
            raise RuntimeError("unexpected Terminan acknowledgement")
        if ack["fill"] is not None:
            submitted_fills.update(canonical_json(ack) + b"\n")
            fill_count += 1

    checkpoint = journal.read_checkpoint()
    if checkpoint != ack:
        raise RuntimeError("Terminan checkpoint readback mismatch")

    restored_fills = sha256()
    for ack in journal.read_fills():
        restored_fills.update(canonical_json(ack) + b"\n")
    if restored_fills.digest() != submitted_fills.digest():
        raise RuntimeError("Terminan fill readback mismatch")
    return {
        "schema": "meta.paper.delivery.receipt.v1",
        "source_sha256": digest,
        "run_id": run_id,
        "checkpoint": checkpoint["checkpoint"],
        "fill_count": fill_count,
        "fills_sha256": restored_fills.hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("source_sha256")
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    print(json.dumps(deliver(args.source, args.source_sha256, args.ledger), sort_keys=True))


if __name__ == "__main__":
    main()
