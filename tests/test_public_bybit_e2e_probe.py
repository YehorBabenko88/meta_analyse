"""Offline acceptance checks; never open public sockets."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "public_bybit_e2e_probe.py"
spec = importlib.util.spec_from_file_location("public_bybit_e2e_probe", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def record(**updates):
    value = {
        "snapshots": 1, "false_valid": 0, "callback_errors": 0,
        "unexpected_exits": 0, "stale_symbols": [], "pending_symbols": [],
        "event_budget_exhausted": False,
        "connection_epochs": 1, "symbols": ["BTCUSDT"],
        "snapshot_epoch_by_symbol": {"BTCUSDT": 1},
    }
    value.update(updates)
    return value


def test_good_snapshot_proof():
    assert module.evaluate(record()) == "TRANSPORT_PASS"


def test_no_snapshot_is_blocked():
    assert module.evaluate(record(snapshots=0)) == "BLOCKED"


def test_budget_exhaustion_is_blocked():
    assert module.evaluate(record(event_budget_exhausted=True)) == "BLOCKED"


def test_stale_book_fails_closed():
    assert module.evaluate(record(stale_symbols=["BTCUSDT"])) == "FAIL"


def test_missing_symbol_fails_closed():
    assert module.evaluate(record(pending_symbols=["ETHUSDT"])) == "FAIL"


def test_false_valid_fails_closed():
    assert module.evaluate(record(false_valid=1)) == "FAIL"


def test_callback_failure_fails_closed():
    assert module.evaluate(record(callback_errors=1)) == "FAIL"


def test_unexpected_exit_fails_closed():
    assert module.evaluate(record(unexpected_exits=1)) == "FAIL"


def test_ui_health_never_marks_invalid_book_current():
    assert module.health_state(valid=False, age_seconds=0, max_age_seconds=90) == "UNVERIFIED"


def test_ui_health_marks_silent_feed_stale():
    assert module.health_state(valid=True, age_seconds=91, max_age_seconds=90) == "STALE"


def test_ui_health_missing_timestamp_is_stale():
    assert module.health_state(valid=True, age_seconds=None, max_age_seconds=90) == "STALE"


def test_ui_health_recent_verified_feed_current():
    assert module.health_state(valid=True, age_seconds=1, max_age_seconds=90) == "CURRENT"


def test_transport_verdict_does_not_claim_full_e2e():
    assert module.evaluate(record()) == "TRANSPORT_PASS"


def test_old_epoch_witness_cannot_pass():
    assert module.evaluate(record(connection_epochs=2, symbols=["BTCUSDT"],
        snapshot_epoch_by_symbol={"BTCUSDT": 1})) == "BLOCKED"


def test_detected_failure_precedes_missing_evidence():
    assert module.evaluate(record(snapshots=0, false_valid=1)) == "FAIL"


def test_nonfinite_and_negative_age_never_current():
    for age in (float("nan"), float("inf"), -1):
        assert module.health_state(valid=True, age_seconds=age, max_age_seconds=90) != "CURRENT"


def test_resource_limit_prevents_transport_pass():
    assert module.evaluate(record(resource_budget_exhausted=True)) == "BLOCKED"

import asyncio
from types import SimpleNamespace
import pytest


def frame(kind="snapshot", sequence=1):
    return SimpleNamespace(valid=True, update_id=sequence, sequence=sequence, message_type=kind)


class ScriptedStream:
    silence_timeout = 90
    connection_epoch = 1
    script = ()
    def __init__(self, on_book, on_gap, **kwargs):
        self.on_book, self.on_gap = on_book, on_gap
    async def run(self, symbols, stop):
        for action in self.script:
            if action == "gap":
                self.connection_epoch += 1
                await self.on_gap(symbols, "disconnected")
            else:
                await self.on_book(symbols[0], action, 1)
        await stop.wait()


@pytest.mark.asyncio
async def test_probe_gap_at_exit_cannot_reuse_old_snapshot():
    class Stream(ScriptedStream):
        script = (frame(), "gap")
    result = await module.probe(["BTCUSDT"], 0.01, stream_factory=Stream)
    assert result["pending_symbols"] == ["BTCUSDT"]
    assert result["verdict"] != "TRANSPORT_PASS"


@pytest.mark.asyncio
async def test_probe_requires_actual_snapshot_after_reconnect():
    class Stream(ScriptedStream):
        script = (frame(), "gap", frame("delta", 2))
    result = await module.probe(["BTCUSDT"], 0.01, stream_factory=Stream)
    assert result["false_valid"] == 1
    assert result["verdict"] == "FAIL"


@pytest.mark.asyncio
async def test_probe_recovers_with_new_snapshot_and_bounds_resources():
    class Stream(ScriptedStream):
        script = (frame(), "gap", frame(sequence=10), frame("delta", 11))
    result = await module.probe(["BTCUSDT"], 0.01, stream_factory=Stream,
        resource_sampler=lambda: {"threads": 2, "tasks": 3},
        resource_limits={"threads": 4, "tasks": 8})
    assert result["verdict"] == "TRANSPORT_PASS"
    assert result["snapshot_epoch_by_symbol"] == {"BTCUSDT": 2}
    assert result["resource_peaks"] == {"threads": 2, "tasks": 3}
    assert result["resource_samples"] >= 1
    assert "resource_history" not in result


@pytest.mark.asyncio
async def test_probe_resource_overrun_stops_and_blocks():
    result = await module.probe(["BTCUSDT"], 0.01, stream_factory=ScriptedStream,
        resource_sampler=lambda: {"threads": 9}, resource_limits={"threads": 2})
    assert result["resource_budget_exhausted"]
    assert result["verdict"] == "BLOCKED"


@pytest.mark.asyncio
async def test_early_stream_exit_is_failure():
    class Stream(ScriptedStream):
        async def run(self, symbols, stop):
            return
    result = await module.probe(["BTCUSDT"], 1, stream_factory=Stream)
    assert result["unexpected_exits"] == 1
    assert result["verdict"] == "FAIL"


def test_missing_connection_epoch_is_blocked():
    assert module.evaluate(record(connection_epochs=0)) == "BLOCKED"


@pytest.mark.asyncio
async def test_probe_fake_clock_detects_stale_book():
    now = [1.0]
    class Stream(ScriptedStream):
        async def run(self, symbols, stop):
            await self.on_book(symbols[0], frame(), 1)
            now[0] = 100.0
            await stop.wait()
    result = await module.probe(["BTCUSDT"], 0.01, stream_factory=Stream, clock=lambda: now[0])
    assert result["stale_symbols"] == ["BTCUSDT"]
    assert result["elapsed_seconds"] == 99
    assert result["verdict"] == "FAIL"


@pytest.mark.asyncio
async def test_resource_sample_failure_is_blocked():
    def broken():
        raise OSError("counter unavailable")
    result = await module.probe(["BTCUSDT"], 0.01, stream_factory=ScriptedStream,
                                resource_sampler=broken)
    assert result["resource_budget_exhausted"]
    assert result["verdict"] == "BLOCKED"

@pytest.mark.parametrize("valid,age,bound", [
    ("yes", 0, 90), (True, "0", 90), (True, 0, "90"),
    (True, True, 90), (True, 0, True), (True, 0, None),
])
def test_malformed_health_never_promotes_current(valid, age, bound):
    assert module.health_state(valid=valid, age_seconds=age, max_age_seconds=bound) != "CURRENT"


@pytest.mark.asyncio
@pytest.mark.parametrize("epoch", [True, 0, -1, 1.0, "1"])
async def test_probe_rejects_malformed_callback_epoch(epoch):
    class Stream(ScriptedStream):
        connection_epoch = epoch
        script = (frame(),)
    result = await module.probe(["BTCUSDT"], 0.01, stream_factory=Stream)
    assert result["false_valid"] == 1
    assert result["verdict"] == "FAIL"


@pytest.mark.asyncio
async def test_probe_rejects_regressing_epoch():
    class Stream(ScriptedStream):
        async def run(self, symbols, stop):
            self.connection_epoch = 2
            await self.on_book(symbols[0], frame(), 1)
            self.connection_epoch = 1
            await self.on_book(symbols[0], frame(sequence=2), 1)
            await stop.wait()
    result = await module.probe(["BTCUSDT"], 0.01, stream_factory=Stream)
    assert result["false_valid"] == 1
    assert result["verdict"] == "FAIL"


@pytest.mark.asyncio
async def test_shutdown_timeout_blocks_and_retains_ownership_until_stream_finishes():
    cancelled, release = asyncio.Event(), asyncio.Event()
    class Stream(ScriptedStream):
        script = (frame(),)
        async def run(self, symbols, stop):
            await self.on_book(symbols[0], frame(), 1)
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                await release.wait()
    probing = asyncio.create_task(module.probe(["BTCUSDT"], 0.01,
        stream_factory=Stream, shutdown_timeout=0.01))
    try:
        await asyncio.wait_for(cancelled.wait(), 1)
        assert not probing.done(), "probe abandoned an owned stream task"
    finally:
        release.set()
    result = await asyncio.wait_for(probing, 1)
    assert result["shutdown_budget_exhausted"]
    assert result["verdict"] == "BLOCKED"
