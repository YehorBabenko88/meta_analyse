"""Resumable streaming archive transport with conservative HTTP validation.

Requires a strong ETag and Content-Length for resumable transfers.
When these are absent, callers should use the ordinary atomic downloader.
"""
from __future__ import annotations

from pathlib import Path
import os

from .archive_partial_state import (
    discard_partial, partial_paths, read_partial, save_partial,
)
from .archive_resume import ResumeState, resume_headers, strong_etag, validate_partial_response
from .bybit_archive_download import validate_archive_url


async def download_resumable(session, url: str, destination: str | Path, *,
                             max_bytes: int = 2_000_000_000,
                             chunk_bytes: int = 1 << 20) -> Path:
    validate_archive_url(url)
    if max_bytes < 1 or chunk_bytes < 1:
        raise ValueError("invalid download limits")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial, sidecar = partial_paths(destination)
    state = read_partial(destination, url, max_bytes=max_bytes)
    if state is None:
        discard_partial(destination)
    headers = resume_headers(state) if state is not None else {
        "Accept-Encoding": "identity"
    }
    try:
        async with session.get(url, headers=headers, allow_redirects=False) as response:
            response.raise_for_status()
            if state is not None:
                expected = validate_partial_response(response.status, response.headers, state)
                etag = state.etag
                total = state.total_bytes
                offset = state.offset
            else:
                if response.status != 200:
                    raise ValueError("expected full archive response")
                etag = response.headers.get("ETag")
                total = response.content_length
                if not strong_etag(etag) or total is None or total < 1:
                    raise ValueError("resumable archive requires strong ETag and length")
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise ValueError("compressed HTTP transfer encoding not supported")
                if total > max_bytes:
                    raise ValueError("archive exceeds maximum allowed bytes")
                offset = 0
                expected = total
            if total > max_bytes:
                raise ValueError("archive exceeds maximum allowed bytes")
            transferred = 0
            with partial.open("ab" if state is not None else "wb") as stream:
                async for chunk in response.content.iter_chunked(chunk_bytes):
                    transferred += len(chunk)
                    if transferred > expected:
                        raise ValueError("archive response exceeds declared range")
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if transferred != expected:
                # Preserve only bytes that were actually flushed to disk.
                if transferred > 0:
                    save_partial(destination, url, ResumeState(offset + transferred, etag, total))
                raise ValueError("incomplete archive response; partial retained")
        if partial.stat().st_size != total:
            raise ValueError("archive size mismatch")
        os.replace(partial, destination)
        sidecar.unlink(missing_ok=True)
        return destination
    except BaseException:
        # The last saved sidecar remains authoritative. Unsaved appended bytes
        # cause the next attempt to discard the partial rather than trust it.
        raise
