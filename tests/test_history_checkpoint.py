import json
import pytest

from meta_analyse.history_checkpoint import HistoryCheckpoint, HistoryKey
from meta_analyse.history_progress import Availability, Segment


def test_checkpoint_roundtrip_and_resume(tmp_path):
    cp = HistoryCheckpoint(tmp_path / "history" / "btc.json")
    key = HistoryKey("BTCUSDT", "trades", 0, 1000)
    cp.save(key, [Segment(0, 400, "archive", Availability.AVAILABLE, True, 10),
                  Segment(400, 1000, "bybit", Availability.UNKNOWN, False)])
    assert cp.progress(key).percent == 40
    assert cp.load(key)[0].records == 10
    assert cp.load(HistoryKey("ETHUSDT", "trades", 0, 1000)) == []


def test_checkpoint_rejects_out_of_bounds_without_overwriting(tmp_path):
    cp = HistoryCheckpoint(tmp_path / "state.json")
    key = HistoryKey("BTCUSDT", "ticks", 0, 1000)
    cp.save(key, [Segment(0, 200, "bybit", Availability.AVAILABLE, True)])
    original = cp.path.read_bytes()
    with pytest.raises(ValueError):
        cp.save(key, [Segment(-1, 500, "bybit", Availability.AVAILABLE, True)])
    assert cp.path.read_bytes() == original


def test_checkpoint_does_not_promote_unknown_to_verified(tmp_path):
    cp = HistoryCheckpoint(tmp_path / "state.json")
    key = HistoryKey("BTCUSDT", "candles:M1", 0, 1000)
    cp.save(key, [Segment(0, 1000, "bybit")])
    assert cp.progress(key).percent == 0


def test_invalid_checkpoint_is_not_silently_accepted(tmp_path):
    cp = HistoryCheckpoint(tmp_path / "state.json")
    cp.path.write_text('{"version": 1, "key": {}, "segments": []}', encoding="utf-8")
    key = HistoryKey("BTCUSDT", "trades", 0, 1000)
    assert cp.load(key) == []
    cp.path.write_text('not-json', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        cp.load(key)
