"""Partial HTTP connection ownership via the public trace extension."""
import asyncio
import httpx
import pytest
from meta_analyse.http_client import ManagedAsyncClient


@pytest.mark.asyncio
async def test_partial_stream_cleanup_survives_repeated_cancel_and_preserves_trace():
    connected, closing, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    events = []
    class Stream:
        closed = False
        async def aclose(self):
            closing.set()
            await release.wait()
            self.closed = True
    stream = Stream()
    async def previous(event, info):
        events.append(event)
    async def handle(request):
        await request.extensions['trace']('connection.connect_tcp.complete', {'return_value': stream})
        connected.set()
        await asyncio.Event().wait()
    async with ManagedAsyncClient(transport=httpx.MockTransport(handle)) as client:
        request = client.build_request('GET', 'https://mock.invalid/', extensions={'trace': previous})
        task = asyncio.create_task(client.send(request))
        try:
            await connected.wait()
            task.cancel()
            await closing.wait()
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(0)
            assert not task.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert stream.closed
            assert events == ['connection.connect_tcp.complete']
            assert request.extensions['trace'] is previous
        finally:
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_successful_response_leaves_stream_owned_by_pool():
    class Stream:
        async def aclose(self):
            pytest.fail('successful send must not close the pooled connection')
    async def handle(request):
        await request.extensions['trace']('connection.connect_tcp.complete', {'return_value': Stream()})
        return httpx.Response(200, text='ok')
    async with ManagedAsyncClient(transport=httpx.MockTransport(handle)) as client:
        request = client.build_request('GET', 'https://mock.invalid/')
        response = await client.send(request)
        assert response.text == 'ok'
        assert 'trace' not in request.extensions

@pytest.mark.asyncio
async def test_failed_redirect_does_not_close_previously_pooled_stream():
    class Stream:
        closed = False
        async def aclose(self):
            self.closed = True
    stream = Stream()
    async def handle(request):
        if request.url.path == '/first':
            trace = request.extensions['trace']
            await trace('connection.connect_tcp.complete', {'return_value': stream})
            await trace('http11.send_request_headers.started', {})
            return httpx.Response(302, headers={'location': '/second'})
        raise httpx.ConnectError('redirect connection failed')
    async with ManagedAsyncClient(transport=httpx.MockTransport(handle), follow_redirects=True) as client:
        with pytest.raises(httpx.ConnectError):
            await client.get('https://mock.invalid/first')
        assert not stream.closed
