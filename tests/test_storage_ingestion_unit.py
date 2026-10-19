"""Offline regression tests for historical trade ingestion."""
from datetime import datetime, timezone
from decimal import Decimal
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
