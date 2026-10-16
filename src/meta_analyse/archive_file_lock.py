"""Cross-process advisory lock for a single archive destination.

Uses a stable sibling lock file. The lock is held for the complete download,
validation, and receipt publication transaction.
"""
from __future__ import annotations

from contextlib import contextmanager, asynccontextmanager
import asyncio
import os
from pathlib import Path
import time


@contextmanager
def archive_file_lock(destination: str | Path, *, timeout: float = 120.0):
    if timeout < 0:
        raise ValueError("timeout must be nonnegative")
    path = Path(destination).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                _lock(handle)
                break
            except (BlockingIOError, PermissionError):
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"archive lock timed out: {path}")
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        try:
            yield
        finally:
            _unlock(handle)


def _lock(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@asynccontextmanager
async def async_archive_file_lock(destination: str | Path, *, timeout: float = 120.0):
    """Async-friendly lock: never block the event loop while waiting."""
    if timeout < 0:
        raise ValueError("timeout must be nonnegative")
    path = Path(destination).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        deadline = time.monotonic() + timeout
        acquired = False
        try:
            while not acquired:
                try:
                    _lock(handle)
                    acquired = True
                except (BlockingIOError, PermissionError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"archive lock timed out: {path}")
                    await asyncio.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            yield
        finally:
            if acquired:
                _unlock(handle)
