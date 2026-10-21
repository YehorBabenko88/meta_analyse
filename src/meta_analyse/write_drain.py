"""Cancellation-safe ownership of synchronous database operations.

Cancelling the awaiting coroutine does not cancel a running executor thread.
Keep the coroutine pending until that thread has committed or rolled back.
"""
import asyncio
import logging

LOG = logging.getLogger(__name__)


async def drain_thread_write(func, /, *args, **kwargs):
    task = asyncio.create_task(asyncio.to_thread(func, *args, **kwargs))
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            # Retrieve the error below after the worker is fully finished.
            break
    # Retrieve the result only after the transaction's context manager exits.
    # On cancellation, do not replace cancellation with an exception raised by
    # a background DB operation, but always retrieve/log that exception.
    try:
        result = task.result()
    except Exception:
        if not cancelled:
            raise
        LOG.exception("Database operation failed while shutdown drained cancellation")
        raise asyncio.CancelledError from None
    if cancelled:
        raise asyncio.CancelledError
    return result
