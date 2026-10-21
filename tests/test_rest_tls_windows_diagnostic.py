"""Offline negative tests for the read-only Windows REST TLS diagnostic."""
import importlib.util
from pathlib import Path
import socket
import ssl
import urllib.error
from unittest.mock import patch

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_rest_tls_windows.py"
spec = importlib.util.spec_from_file_location("verify_rest_tls_windows", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_rejects_invalid_timeout():
    for value in (0, -1, 31):
        with pytest.raises(ValueError):
            probe.run(value)


def test_dns_failure_does_not_attempt_http():
    with patch.object(probe.socket, "getaddrinfo", side_effect=socket.gaierror("mock DNS failure")), \
         patch.object(probe.urllib.request, "urlopen") as urlopen:
        report = probe.run(0.2)
    assert not report["steps"]["dns"]["ok"]
    urlopen.assert_not_called()


@pytest.mark.parametrize("failure", [
    urllib.error.URLError("mock proxy failure"),
    TimeoutError("mock connect timeout"),
    ssl.SSLError("mock handshake failure"),
    ssl.SSLCertVerificationError("mock untrusted certificate"),
])
def test_https_failures_are_reported_without_tls_bypass(failure):
    with patch.object(probe.socket, "getaddrinfo", return_value=[
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
    ]), patch.object(probe.socket, "socket", side_effect=OSError("mock direct connect failure")), \
         patch.object(probe.urllib.request, "urlopen", side_effect=failure) as urlopen:
        report = probe.run(0.2)
    assert report["steps"]["https"]["ok"] is False
    assert report["trust"]["check_hostname"] is True
    assert report["trust"]["verify_mode"] == ssl.CERT_REQUIRED
    assert urlopen.call_args.kwargs["timeout"] == 0.2
    assert urlopen.call_args.kwargs["context"].check_hostname is True
    assert urlopen.call_args.kwargs["context"].verify_mode == ssl.CERT_REQUIRED
