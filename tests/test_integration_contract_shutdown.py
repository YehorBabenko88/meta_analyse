"""Cancellation during a blocking write must not release shutdown ownership."""
import asyncio
import threading
import pytest
from meta_analyse.write_drain import drain_thread_write


@pytest.mark.asyncio
async def test_shutdown_waits_for_thread_write_before_cancelled_task_finishes():
    entered, release = threading.Event(), threading.Event()
    writes = []
    def commit():
        entered.set()
        if not release.wait(5):
            raise TimeoutError("test did not release write")
        writes.append("committed")
    task = asyncio.create_task(drain_thread_write(commit))
    assert await asyncio.to_thread(entered.wait, 3)
    task.cancel()
    await asyncio.sleep(0.02)
    assert not task.done(), "shutdown lost ownership of a live DB write"
    assert not writes
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 3)
    assert writes == ["committed"]


@pytest.mark.asyncio
async def test_repeated_cancellation_does_not_abandon_write():
    entered, release = threading.Event(), threading.Event()
    def commit():
        entered.set()
        if not release.wait(5):
            raise TimeoutError("write stuck")
    task = asyncio.create_task(drain_thread_write(commit))
    assert await asyncio.to_thread(entered.wait, 3)
    for _ in range(3):
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 3)


@pytest.mark.asyncio
async def test_failed_write_after_cancellation_waits_for_rollback(caplog):
    entered, release, rolled_back = threading.Event(), threading.Event(), threading.Event()
    def fail_and_rollback():
        entered.set()
        if not release.wait(5):
            raise TimeoutError("write stuck")
        try:
            raise ValueError("simulated transaction failure")
        finally:
            rolled_back.set()
    task = asyncio.create_task(drain_thread_write(fail_and_rollback))
    assert await asyncio.to_thread(entered.wait, 3)
    task.cancel()
    await asyncio.sleep(0.01)
    assert not task.done()
    assert not rolled_back.is_set()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 3)
    assert rolled_back.is_set()
    assert "Database operation failed" in caplog.text


@pytest.mark.asyncio
async def test_write_failure_without_cancellation_is_propagated():
    def fail():
        raise ValueError("database rollback")
    with pytest.raises(ValueError, match="database rollback"):
        await drain_thread_write(fail)


@pytest.mark.asyncio
async def test_successful_write_returns_result():
    assert await drain_thread_write(lambda: 42) == 42
