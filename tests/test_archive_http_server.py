"""Loopback HTTP integration test: interrupted stream and byte-range recovery."""
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from meta_analyse.archive_resumable_download import download_resumable
from meta_analyse.archive_partial_state import partial_paths

URL = "https://public.bybit.com/trading/BTCUSDT/BTCUSDT2025-01-01.csv.gz"


@pytest.mark.asyncio
async def test_local_http_disconnect_then_resume(tmp_path):
    aiohttp = pytest.importorskip("aiohttp")
    payload = b"abcdef" * 2048
    seen_ranges = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requested = self.headers.get("Range")
            seen_ranges.append(requested)
            if requested is None:
                self.send_response(200)
                self.send_header("ETag", '"v1"')
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload[:4096])
                self.wfile.flush()
                self.connection.shutdown(2)
                self.close_connection = True
                return
            assert requested == "bytes=4096-"
            assert self.headers.get("If-Range") == '"v1"'
            self.send_response(206)
            self.send_header("ETag", '"v1"')
            self.send_header("Content-Length", str(len(payload) - 4096))
            self.send_header("Content-Range", f"bytes 4096-{len(payload)-1}/{len(payload)}")
            self.end_headers()
            self.wfile.write(payload[4096:])

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # The transport validates the pinned public Bybit URL. Redirect only
        # the session's socket connection to the loopback test server.
        class LocalSession:
            def __init__(self, session):
                self.session = session

            def get(self, url, **kwargs):
                assert url == URL
                return self.session.get(
                    f"http://127.0.0.1:{server.server_port}/archive",
                    **kwargs,
                )

        destination = tmp_path / "archive.csv.gz"
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as raw_session:
            session = LocalSession(raw_session)
            with pytest.raises((aiohttp.ClientError, asyncio.TimeoutError)):
                await download_resumable(session, URL, destination, chunk_bytes=1024)
            partial, sidecar = partial_paths(destination)
            assert partial.read_bytes() == payload[:4096]
            assert sidecar.exists()
            await download_resumable(session, URL, destination, chunk_bytes=1024)
        assert destination.read_bytes() == payload
        assert seen_ranges == [None, "bytes=4096-"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
