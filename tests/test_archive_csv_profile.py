"""Shared CSV acceptance profile for archive audit and storage importer."""
import gzip

import pytest

from meta_analyse.bybit_archive_audit import audit_trade_gzip


HEADER = "trdMatchID,timestamp,price,size,side\n"
GOOD = "id1,1735689600.123456,100.5,1.25,Buy\n"


@pytest.mark.parametrize(
    ("csv_text", "valid"),
    [
        (HEADER + GOOD, True),
        ("\ufeff" + HEADER + GOOD, True),
        ("timestamp,price,size\n1735689600,100,1\n", False),
        ("trdMatchID,timestamp,price,size,side,side\n" + "id1,1735689600,100,1,Buy,Buy\n", False),
        (HEADER + "id1,1735689600,100,1,Buy,extra\n", False),
        (HEADER + ",1735689600,100,1,Buy\n", False),
        (HEADER + "id1,1735689600,100,1,Unknown\n", False),
        (HEADER + "id1,1735689600,100,0,Buy\n", False),
        (HEADER + "id1,253402300800,100,1,Buy\n", False),
        (HEADER + "id1,1735689601,100,1,Buy\nid2,1735689600,100,1,Sell\n", False),
        (HEADER, False),
    ],
)
def test_archive_csv_strict_profile(tmp_path, csv_text, valid):
    path = tmp_path / "trades.csv.gz"
    path.write_bytes(gzip.compress(csv_text.encode("utf-8")))
    result = audit_trade_gzip(path)
    assert result.valid is valid, result.reason
    assert result.complete is False
