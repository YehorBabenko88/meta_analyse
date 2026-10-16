from datetime import date
import csv
import gzip

import pytest

from meta_analyse.archive_ingestion import acquire_archive

URL = "https://public.bybit.com/trading/BTCUSDT/BTCUSDT2025-01-01.csv.gz"


def write_day(path, timestamp):
    with gzip.open(path, "wt", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["timestamp", "price", "size"])
        writer.writeheader()
        writer.writerow({"timestamp": timestamp, "price": "100", "size": "1"})


@pytest.mark.asyncio
async def test_day_validation_and_day_bound_cache(tmp_path, monkeypatch):
    from meta_analyse import archive_ingestion
    path = tmp_path / "trades.csv.gz"
    calls = []

    async def download(session, url, destination, **kwargs):
        calls.append(url)
        write_day(destination, "1735689600")
        return destination

    monkeypatch.setattr(archive_ingestion, "download_archive", download)
    day = date(2025, 1, 1)
    receipt = await acquire_archive(object(), URL, path, day=day)
    assert receipt.day == "2025-01-01"
    assert not receipt.complete
    assert await acquire_archive(object(), URL, path, day=day) == receipt
    assert len(calls) == 1
    with pytest.raises(ValueError, match="outside"):
        await acquire_archive(object(), URL, path, day=date(2025, 1, 2))
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_out_of_day_archive_never_writes_receipt(tmp_path, monkeypatch):
    from meta_analyse import archive_ingestion
    path = tmp_path / "trades.csv.gz"

    async def download(session, url, destination, **kwargs):
        write_day(destination, "1735776000")
        return destination

    monkeypatch.setattr(archive_ingestion, "download_archive", download)
    with pytest.raises(ValueError, match="outside"):
        await acquire_archive(object(), URL, path, day=date(2025, 1, 1))
    assert not (tmp_path / "trades.csv.gz.audit.json").exists()
