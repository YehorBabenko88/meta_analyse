"""Keep the coroutine owning a DB write alive until its worker thread finishes.

Cancellation cannot stop asyncio.to_thread; propagating it before the thread
finishes lets shutdown close resources while a transaction is still active.
"""
import asyncio


async def drain_thread_write(func, /, *args, **kwargs):
    task = asyncio.create_task(asyncio.to_thread(func, *args, **kwargs))
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            cancelled = True
            if task.done():
                break
    if cancelled:
        # Surface failures through the task while preserving cancellation.
        if not task.cancelled():
            task.exception()
        raise asyncio.CancelledError
    return result
