import pytest

from meta_analyse.trade_archive_audit import audit_trade_csv


def test_valid_rows_do_not_prove_complete_archive(tmp_path):
    path = tmp_path / "trades.csv"
    path.write_text("timestamp,price,size\n100,2,1\n200,3,4\n")
    result = audit_trade_csv(path, 0, 300)
    assert result.rows == 2
    assert result.first_ms == 100
    assert result.last_ms == 200
    assert result.chronology_ok
    assert not result.complete


@pytest.mark.parametrize("body", [
    "timestamp,price,size\n200,2,1\n100,3,1\n",
    "timestamp,price,size\n300,2,1\n",
    "timestamp,price,size\n100,-2,1\n",
    "timestamp,price,size\n100,NaN,1\n",
    "timestamp,price,size\n100,2,0\n",
    "timestamp,price,size\nwrong,2,1\n",
])
def test_invalid_rows_rejected(tmp_path, body):
    path = tmp_path / "trades.csv"
    path.write_text(body)
    with pytest.raises(ValueError):
        audit_trade_csv(path, 0, 300)
