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
    }
    value.update(updates)
    return value


def test_good_snapshot_proof():
    assert module.evaluate(record()) == "PASS"


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
