"""Async and cross-process destination lock regression tests."""
import asyncio
import multiprocessing
import time

import pytest

from meta_analyse.archive_file_lock import archive_file_lock, async_archive_file_lock


def _hold_lock(path, ready, release):
    with archive_file_lock(path):
        ready.set()
        release.wait(10)


@pytest.mark.asyncio
async def test_async_lock_serializes_tasks(tmp_path):
    target = tmp_path / "trades.csv.gz"
    events = []

    async def worker(name):
        async with async_archive_file_lock(target):
            events.append((name, "start"))
            await asyncio.sleep(0.02)
            events.append((name, "end"))

    await asyncio.gather(worker("a"), worker("b"))
    assert len(events) == 4
    assert events[0][0] == events[1][0]
    assert events[2][0] == events[3][0]
    assert events[0][0] != events[2][0]


@pytest.mark.asyncio
async def test_lock_timeout_across_processes(tmp_path):
    target = tmp_path / "trades.csv.gz"
    ctx = multiprocessing.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    process = ctx.Process(target=_hold_lock, args=(target, ready, release))
    process.start()
    try:
        assert await asyncio.to_thread(ready.wait, 5)
        with pytest.raises(TimeoutError):
            async with async_archive_file_lock(target, timeout=0.1):
                pytest.fail("lock unexpectedly acquired")
    finally:
        release.set()
        await asyncio.to_thread(process.join, 5)
        if process.is_alive():
            process.terminate()
            await asyncio.to_thread(process.join, 5)
    assert process.exitcode == 0


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_hold_lock(tmp_path):
    target = tmp_path / "trades.csv.gz"
    async with async_archive_file_lock(target):
        waiter = asyncio.create_task(_wait_for_lock(target))
        await asyncio.sleep(0.05)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
    async with async_archive_file_lock(target, timeout=0.2):
        pass


async def _wait_for_lock(target):
    async with async_archive_file_lock(target):
        return True


@pytest.mark.asyncio
async def test_waiting_process_acquires_lock_after_release(tmp_path):
    """A separate process releases the lock while an async waiter is pending."""
    target = tmp_path / "trades.csv.gz"
    ctx = multiprocessing.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    process = ctx.Process(target=_hold_lock, args=(target, ready, release))
    process.start()
    try:
        assert await asyncio.to_thread(ready.wait, 5)
        waiter = asyncio.create_task(_wait_for_lock(target))
        await asyncio.sleep(0.05)
        assert not waiter.done()
        release.set()
        assert await asyncio.wait_for(waiter, timeout=5) is True
    finally:
        release.set()
        await asyncio.to_thread(process.join, 5)
        if process.is_alive():
            process.terminate()
            await asyncio.to_thread(process.join, 5)
    assert process.exitcode == 0
