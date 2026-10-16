"""Bounded archive download + validation, with durable local audit receipts.

A successful receipt confirms parsing of the downloaded file, never completeness
of historical market trades. The receipt is tied to file bytes via SHA-256.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path

from .bybit_archive_audit import audit_trade_gzip
from .bybit_archive_download import download_archive, validate_archive_url
from .history_parallel import bounded_map


@dataclass(frozen=True)
class ArchiveReceipt:
    url: str
    sha256: str
    bytes: int
    rows: int
    first_ms: int | None
    last_ms: int | None
    valid: bool
    complete: bool = False


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _receipt_path(path: Path) -> Path:
    return path.with_name(path.name + ".audit.json")


def _load_receipt(path: Path, url: str) -> ArchiveReceipt | None:
    try:
        data = json.loads(_receipt_path(path).read_text(encoding="utf-8"))
        receipt = ArchiveReceipt(**data)
        if (receipt.url == url and receipt.valid and not receipt.complete
                and path.stat().st_size == receipt.bytes
                and _digest(path) == receipt.sha256):
            return receipt
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return None


def _write_receipt(path: Path, receipt: ArchiveReceipt) -> None:
    dest = _receipt_path(path)
    temporary = dest.with_name(dest.name + ".partial")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(asdict(receipt), stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, dest)
    finally:
        temporary.unlink(missing_ok=True)


async def acquire_archive(session, url: str, path: str | Path, *,
                          max_bytes: int = 2_000_000_000) -> ArchiveReceipt:
    validate_archive_url(url)
    path = Path(path)
    if path.is_file():
        cached = await asyncio.to_thread(_load_receipt, path, url)
        if cached is not None:
            return cached
    await download_archive(session, url, path, max_bytes=max_bytes)
    audit = await asyncio.to_thread(audit_trade_gzip, path)
    if not audit.valid:
        raise ValueError(f"archive rejected: {audit.reason}")
    size, digest = await asyncio.to_thread(lambda: (path.stat().st_size, _digest(path)))
    receipt = ArchiveReceipt(url, digest, size, audit.rows, audit.first_ms,
                             audit.last_ms, True, False)
    await asyncio.to_thread(_write_receipt, path, receipt)
    return receipt


async def acquire_many(archives: list[tuple[str, str | Path]], *,
                       concurrency: int = 4, max_bytes: int = 2_000_000_000):
    import aiohttp
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=120)
    connector = aiohttp.TCPConnector(limit=max(1, concurrency))
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        async def worker(entry):
            return await acquire_archive(session, entry[0], entry[1], max_bytes=max_bytes)
        return await bounded_map(archives, worker, concurrency=concurrency)
