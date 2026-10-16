"""HTTPX client retaining ownership of sockets during connection setup."""
from __future__ import annotations
import asyncio
import httpx


class ManagedAsyncClient(httpx.AsyncClient):
    """Close a connected stream if cancellation interrupts TLS before pool ownership.

    httpcore 1.0.9's AnyIOStream.start_tls catches Exception, excluding
    asyncio.CancelledError. Its HTTPConnection cannot close that partial stream.
    The public trace extension exposes it without accessing transport internals.
    """
    async def send(self, request, **kwargs):
        stream = None
        previous_trace = request.extensions.get('trace')

        async def trace(event, info):
            nonlocal stream
            if event.endswith(('.connect_tcp.complete', '.connect_unix_socket.complete',
                               '.start_tls.complete')):
                stream = info['return_value']
            # Protocol operations already have a pool-owned connection. Do not
            # retain it across redirects or HTTP/2 sharing by another request.
            handed_off = event in ('http11.send_request_headers.started',
                                   'http2.send_connection_init.started',
                                   'http2.send_request_headers.started')
            if handed_off:
                stream = None
            if previous_trace is not None:
                await previous_trace(event, info)
            if event.endswith('.start_tls.complete'):
                stream = None

        request.extensions['trace'] = trace
        try:
            return await super().send(request, **kwargs)
        except BaseException:
            if stream is not None:
                cleanup = asyncio.create_task(stream.aclose())
                while not cleanup.done():
                    try:
                        await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        pass
                cleanup.result()
            raise
        finally:
            stream = None
            if previous_trace is None:
                request.extensions.pop('trace', None)
            else:
                request.extensions['trace'] = previous_trace
