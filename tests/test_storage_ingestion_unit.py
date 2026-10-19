"""Offline regression tests for historical trade ingestion."""
from datetime import datetime, timezone
from decimal import Decimal
import csv
import gzip
import hashlib

import pytest

from meta_analyse.archive_db_import import parse_trade, import_verified_archive, file_sha256


def test_parse_trade_exact_fraction():
    trade_id, ts, price, qty, side = parse_trade({
        "trdMatchID":"a", "timestamp":"1720000000.123456",
        "price":"100.01", "size":"2.5", "side":"Buy"})
    assert trade_id == "a"
    assert ts.microsecond == 123456
    assert price == Decimal("100.01")
    assert qty == Decimal("2.5")
    assert side == "Buy"


@pytest.mark.parametrize("changes", [
    {"trdMatchID":""}, {"timestamp":"NaN"}, {"timestamp":"1e999999"},
    {"price":"-1"}, {"size":"Infinity"}, {"side":"Unknown"},
])
def test_invalid_trade(changes):
    row = {"trdMatchID":"a","timestamp":"1720000000","price":"1","size":"2","side":"Sell"}
    row.update(changes)
    with pytest.raises(ValueError):
        parse_trade(row)


def test_invalid_receipt_rejected_before_db(tmp_path):
    path = tmp_path / "trades.csv"
    path.write_text("timestamp,trdMatchID,price,size,side\n1720000000,a,1,2,Buy\n")
    receipt = {"valid":True,"complete":False,"url":"https://example.invalid/archive",
               "sha256":file_sha256(path),"bytes":path.stat().st_size,"rows":1}
    for change in ({"rows":True},{"bytes":False},{"complete":True},
                   {"sha256":"bad"},{"rows":2},{"url":"  "}):
        candidate = dict(receipt, **change)
        with pytest.raises(ValueError):
            import_verified_archive(None,path,candidate,symbol="BTCUSDT")


def test_gzip_row_budget_before_db(tmp_path):
    path = tmp_path / "trades.gz"
    with gzip.open(path,"wt") as f:
        f.write("timestamp,trdMatchID,price,size,side\n")
        f.write("1720000000,a,1,2,Buy\n1720000001,b,1,2,Sell\n")
    receipt = {"valid":True,"complete":False,"url":"https://example.invalid/archive",
               "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
               "bytes":path.stat().st_size,"rows":1}
    with pytest.raises(ValueError,match="audited row count"):
        import_verified_archive(None,path,receipt,symbol="BTCUSDT")


def test_timestamp_exact_microseconds_ignores_decimal_context():
    from decimal import localcontext
    row = {"trdMatchID": "precision", "timestamp": "1735689600.123456999999999999999999",
           "price": "1", "size": "1", "side": "Buy"}
    with localcontext() as context:
        context.prec = 8
        _, result, _, _, _ = parse_trade(row)
    assert result == datetime(2025, 1, 1, 0, 0, 0, 123456, tzinfo=timezone.utc)


@pytest.mark.parametrize("value,expected", [
    ("1735689599.999999999999999999", datetime(2024, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)),
    ("1735689600.000000999999999999", datetime(2025, 1, 1, tzinfo=timezone.utc)),
])
def test_timestamp_utc_day_boundary_without_rounding(value, expected):
    from decimal import localcontext
    row = {"trdMatchID": "boundary", "timestamp": value,
           "price": "1", "size": "1", "side": "Sell"}
    with localcontext() as context:
        context.prec = 8
        assert parse_trade(row)[1] == expected


@pytest.mark.parametrize("timestamps,valid", [
    (("1735689600.000900", "1735689600.000100"), False),
    (("1735689600.000100", "1735689600.000900"), True),
    (("1735689600.000100", "1735689600.000100"), True),
])
def test_import_preflight_raw_decimal_timestamp_order(tmp_path, timestamps, valid):
    path = tmp_path / "trades.csv"
    path.write_text("timestamp,trdMatchID,price,size,side\n" +
                    "".join(f"{ts},id{i},1,1,Buy\n" for i, ts in enumerate(timestamps)))
    receipt = {"valid": True, "complete": False, "url": "https://example.invalid/archive",
               "sha256": file_sha256(path), "bytes": path.stat().st_size, "rows": 2}
    if not valid:
        with pytest.raises(ValueError, match="decreasing raw trade timestamp"):
            import_verified_archive(None, path, receipt, symbol="BTCUSDT")
    else:
        # Valid chronological rows must pass CSV preflight and reach DB setup.
        with pytest.raises((AttributeError, TypeError)):
            import_verified_archive(None, path, receipt, symbol="BTCUSDT")


@pytest.mark.parametrize("content", [
    "timestamp,trdMatchID,price,size,side\n1,id,1,1\n",
    "timestamp,trdMatchID,price,size,side\n1,id,1,0,Buy\n",
])
def test_import_preflight_rejects_missing_field_or_zero_size(tmp_path, content):
    path = tmp_path / "trades.csv"
    path.write_text(content)
    receipt = {"valid": True, "complete": False, "url": "https://example.invalid/archive",
               "sha256": file_sha256(path), "bytes": path.stat().st_size, "rows": 1}
    with pytest.raises(ValueError):
        import_verified_archive(None, path, receipt, symbol="BTCUSDT")


def test_import_rejects_malformed_csv_quoting_before_db(tmp_path):
    path = tmp_path / "malformed.csv"
    path.write_text('timestamp,trdMatchID,price,size,side\n"1735689600,id,1,1,Buy\n')
    receipt = {"valid": True, "complete": False,
               "url": "https://example.invalid/malformed",
               "sha256": file_sha256(path), "bytes": path.stat().st_size, "rows": 1}
    with pytest.raises(csv.Error):
        import_verified_archive(None, path, receipt, symbol="BTCUSDT")


@pytest.mark.parametrize("change", [{"rows": 0}, {"bytes": 0}])
def test_empty_receipt_is_rejected_before_database(tmp_path, change):
    path = tmp_path / "trades.csv"
    path.write_text("timestamp,trdMatchID,price,size,side\n1,id,1,1,Buy\n")
    receipt = {"valid": True, "complete": False, "url": "https://example.invalid/archive",
               "sha256": file_sha256(path), "bytes": path.stat().st_size, "rows": 1}
    with pytest.raises(ValueError, match="invalid receipt"):
        import_verified_archive(None, path, dict(receipt, **change), symbol="BTCUSDT")


@pytest.mark.parametrize("value", [
    "253402300800", "253402300800.000000000001", "-0.000000001",
])
def test_timestamp_outside_utc_range_rejected(value):
    with pytest.raises(ValueError, match="timestamp out of range"):
        parse_trade({"trdMatchID": "boundary", "timestamp": value,
                     "price": "1", "size": "1", "side": "Buy"})


def test_timestamp_max_supported_microsecond():
    row = {"trdMatchID": "max", "timestamp": "253402300799.999999999999999999",
           "price": "1", "size": "1", "side": "Sell"}
    assert parse_trade(row)[1] == datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)


@pytest.mark.parametrize("content", [
    "timestamp,trdMatchID,price,size,side\n1,id,1,1,Buy,extra\n",
    "timestamp,trdMatchID,price,size,side\n1,id,1,1,Buy\n2,id2,1,1\n",
    "timestamp,trdMatchID,price,size,side,side\n1,id,1,1,Buy,Buy\n",
])
def test_import_rejects_csv_shape_violations_before_db(tmp_path, content):
    path = tmp_path / "invalid.csv"
    path.write_text(content)
    receipt = {"valid": True, "complete": False,
               "url": "https://example.invalid/invalid",
               "sha256": file_sha256(path), "bytes": path.stat().st_size,
               "rows": content.count("\n") - 1}
    with pytest.raises(ValueError):
        import_verified_archive(None, path, receipt, symbol="BTCUSDT")
