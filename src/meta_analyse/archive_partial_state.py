"""Durable metadata for conservative resumable archive downloads.

A partial is reusable only when its URL, strong ETag and byte count match
the sidecar. This module does not perform network requests or promote files.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path

from .archive_resume import ResumeState, resume_headers


@dataclass(frozen=True)
class PartialMetadata:
    url: str
    etag: str
    total_bytes: int
    offset: int


def partial_paths(destination: str | Path) -> tuple[Path, Path]:
    dest = Path(destination)
    return (dest.with_name(dest.name + ".partial"),
            dest.with_name(dest.name + ".partial.json"))


def read_partial(destination: str | Path, url: str, *,
                 max_bytes: int = 2_000_000_000) -> ResumeState | None:
    partial, sidecar = partial_paths(destination)
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        metadata = PartialMetadata(**data)
        state = ResumeState(metadata.offset, metadata.etag, metadata.total_bytes)
        resume_headers(state)
        if (metadata.url != url or metadata.total_bytes > max_bytes
                or partial.stat().st_size != metadata.offset):
            return None
        return state
    except (OSError, ValueError, TypeError, KeyError):
        return None


def save_partial(destination: str | Path, url: str, state: ResumeState) -> None:
    resume_headers(state)
    partial, sidecar = partial_paths(destination)
    if partial.stat().st_size != state.offset:
        raise ValueError("partial file size does not match saved offset")
    metadata = PartialMetadata(url, state.etag, state.total_bytes, state.offset)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    temporary = sidecar.with_name(sidecar.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(asdict(metadata), stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, sidecar)
    finally:
        temporary.unlink(missing_ok=True)


def discard_partial(destination: str | Path) -> None:
    partial, sidecar = partial_paths(destination)
    sidecar.unlink(missing_ok=True)
    partial.unlink(missing_ok=True)
