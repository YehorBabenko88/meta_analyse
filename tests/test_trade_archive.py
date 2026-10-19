import hashlib
import pytest

from meta_analyse.trade_archive import ArchiveManifest, verify_archive


def test_archive_digest_is_not_semantic_completeness(tmp_path):
    data = b"timestamp,price,size\n1,100,2\n"
    path = tmp_path / "trades.csv"
    path.write_bytes(data)
    manifest = ArchiveManifest("BTCUSDT", "trades", 0, 1000,
                               hashlib.sha256(data).hexdigest(), len(data), "trusted-archive")
    result = verify_archive(path, manifest)
    assert not result.verified
    assert result.records == 0
    assert verify_archive(path, manifest, verified_records=1).verified


def test_archive_corruption_rejected(tmp_path):
    path = tmp_path / "ticks.csv"
    path.write_bytes(b"corrupted")
    manifest = ArchiveManifest("ETHUSDT", "ticks", 0, 1000, "0" * 64, 9, "archive")
    with pytest.raises(ValueError, match="checksum"):
        verify_archive(path, manifest)
