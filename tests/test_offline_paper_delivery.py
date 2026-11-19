from contextlib import closing
import json
from hashlib import sha256
import sqlite3

import pytest
from terminan.paper_journal import PaperJournal

from meta_analyse.offline_paper_delivery import deliver


def source(tmp_path):
    events = [
        ("enabled", "00:00:00", {"enabled": True}),
        ("closed_minute", "00:00:00", {"poc": "100", "complete": True}),
        ("trade", "00:01:01", {"price": "102"}),
        ("trade", "00:01:02", {"price": "100"}),
    ]
    payload = {
        "schema": "meta.paper.source.v1",
        "source_id": "meta-fixture",
        "symbol": "BTCUSDT",
        "events": [
            {"schema": "terminan.paper.event.v1", "sequence": sequence,
             "kind": kind, "event_time": f"2026-11-19T{clock}+00:00", **values}
            for sequence, (kind, clock, values) in enumerate(events, 1)
        ],
    }
    path = tmp_path / "source.json"
    raw = json.dumps(payload).encode()
    path.write_bytes(raw)
    return path, sha256(raw).hexdigest()


@pytest.mark.parametrize("after_commit", [False, True])
def test_reopened_delivery_recovers_one_fill_and_same_cursor(tmp_path, monkeypatch, after_commit):
    path, digest = source(tmp_path)
    target = tmp_path / "ledger.sqlite3"
    submit = PaperJournal.submit

    def interrupted(journal, event):
        if event["sequence"] != 4:
            return submit(journal, event)
        if after_commit:
            submit(journal, event)
        raise OSError("interrupted delivery")

    with monkeypatch.context() as patch:
        patch.setattr(PaperJournal, "submit", interrupted)
        with pytest.raises(OSError, match="interrupted delivery"):
            deliver(path, digest, target)

    receipt = deliver(path, digest, target)
    assert receipt["checkpoint"] == 4
    assert receipt["fill_count"] == 1
    assert receipt["source_sha256"] == digest
    assert deliver(path, digest, target) == receipt
    assert sha256(path.read_bytes()).hexdigest() == digest

    restored = tmp_path / "restored.sqlite3"
    with closing(sqlite3.connect(target)) as original, closing(sqlite3.connect(restored)) as backup:
        original.backup(backup)
    assert deliver(path, digest, restored) == receipt


def test_changed_source_is_refused_before_creating_ledger(tmp_path):
    path, digest = source(tmp_path)
    path.write_bytes(path.read_bytes() + b" ")
    target = tmp_path / "ledger.sqlite3"
    with pytest.raises(ValueError, match="source digest mismatch"):
        deliver(path, digest, target)
    assert not target.exists()
