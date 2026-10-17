import csv
import gzip

import pytest

from meta_analyse.archive_ingestion import acquire_archive


URL = "https://public.bybit.com/trading/BTCUSDT/BTCUSDT2025-01-01.csv.gz"


def make_gzip(path):
    with gzip.open(path, "wt", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["timestamp", "price", "size"])
        writer.writeheader()
        writer.writerow({"timestamp": "1735689600", "price": "100", "size": "2"})


@pytest.mark.asyncio
async def test_cached_receipt_skips_network_and_detects_tampering(tmp_path, monkeypatch):
    from meta_analyse import archive_ingestion
    path = tmp_path / "archive.csv.gz"
    make_gzip(path)
    calls = []

    async def fake_download(session, url, dest, **kwargs):
        calls.append(url)
        make_gzip(dest)
        return dest

    monkeypatch.setattr(archive_ingestion, "download_archive", fake_download)
    first = await acquire_archive(object(), URL, path)
    assert first.valid and not first.complete and first.rows == 1
    assert len(calls) == 1
    second = await acquire_archive(object(), URL, path)
    assert second == first and len(calls) == 1
    path.write_bytes(b"tampered")
    third = await acquire_archive(object(), URL, path)
    assert third == first and len(calls) == 2


@pytest.mark.asyncio
async def test_invalid_archive_never_receives_audit_receipt(tmp_path, monkeypatch):
    from meta_analyse import archive_ingestion
    path = tmp_path / "bad.csv.gz"

    async def fake_download(session, url, dest, **kwargs):
        dest.write_bytes(b"invalid gzip")
        return dest

    monkeypatch.setattr(archive_ingestion, "download_archive", fake_download)
    with pytest.raises(ValueError, match="archive rejected"):
        await acquire_archive(object(), URL, path)
    assert not (tmp_path / "bad.csv.gz.audit.json").exists()


@pytest.mark.asyncio
async def test_failed_replacement_removes_stale_receipt(tmp_path, monkeypatch):
    from meta_analyse import archive_ingestion

    path = tmp_path / "archive.csv.gz"
    receipt_path = tmp_path / "archive.csv.gz.audit.json"
    calls = []

    async def fake_download(session, url, dest, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            make_gzip(dest)
        else:
            dest.write_bytes(b"not a gzip archive")
        return dest

    monkeypatch.setattr(archive_ingestion, "download_archive", fake_download)
    await acquire_archive(object(), URL, path)
    assert receipt_path.exists()
    # Change the existing file so the cached receipt is no longer trusted.
    path.write_bytes(b"changed after audit")
    with pytest.raises(ValueError, match="archive rejected"):
        await acquire_archive(object(), URL, path)
    assert len(calls) == 2
    assert not receipt_path.exists()
