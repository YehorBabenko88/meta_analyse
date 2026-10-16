"""Offline validation of trade archive manifests.

A successful HTTP response or archive filename alone is never proof of
completeness. Every declared interval must have trusted provenance, a digest,
and independently verified records before contributing to coverage.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from pathlib import Path

from .history_progress import Availability, Segment


@dataclass(frozen=True)
class ArchiveManifest:
    symbol: str
    kind: str
    start_ms: int
    end_ms: int
    sha256: str
    expected_bytes: int
    source: str


def verify_archive(path: str | Path, manifest: ArchiveManifest, *, verified_records: int | None = None) -> Segment:
    """Verify bytes and metadata, not semantic tick completeness."""
    if not manifest.symbol or manifest.kind not in ("trades", "ticks"):
        raise ValueError("invalid archive identity")
    if manifest.start_ms >= manifest.end_ms or manifest.expected_bytes < 0:
        raise ValueError("invalid archive interval or size")
    if len(manifest.sha256) != 64 or any(c not in "0123456789abcdef" for c in manifest.sha256.lower()):
        raise ValueError("invalid SHA-256")
    file = Path(path)
    digest = hashlib.sha256()
    size = 0
    with file.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    if size != manifest.expected_bytes or digest.hexdigest() != manifest.sha256.lower():
        raise ValueError("archive size or checksum mismatch")
    # A matching digest proves only byte integrity. Semantic completeness
    # must be verified separately (sequence/timestamps/source guarantees).
    validated = verified_records is not None and verified_records >= 0
    return Segment(manifest.start_ms, manifest.end_ms, manifest.source,
                   Availability.AVAILABLE, validated, verified_records or 0)
