"""Read-only Windows Bybit TLS probe. Python 3.12 stdlib, no API keys."""
import argparse
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlsplit

HOST = "api.bybit.com"
URL = "https://api.bybit.com/v5/market/time"

def run(timeout=8.0):
    if not (0 < timeout <= 30):
        raise ValueError("timeout must be between 0 and 30 seconds")
    report = {"utc": datetime.now(timezone.utc).isoformat(), "python": sys.version.split()[0],
              "host": HOST, "url": URL, "tls_verification": "required",
              "proxy_environment_present": {k: bool(os.environ.get(k)) for k in
                  ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy",
                   "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy")},
              "steps": {}}
    try:
        answers = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
        report["steps"]["dns"] = {"ok": True, "ipv4": sorted({a[4][0] for a in answers if a[0] == socket.AF_INET}),
                                     "ipv6": sorted({a[4][0] for a in answers if a[0] == socket.AF_INET6})}
    except (OSError, socket.gaierror) as exc:
        report["steps"]["dns"] = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}
        return report
    context = ssl.create_default_context()
    report["trust"] = {"verify_mode": context.verify_mode, "check_hostname": context.check_hostname,
                       "default_verify_paths": str(ssl.get_default_verify_paths())}
    for family, name in ((socket.AF_INET, "ipv4"), (socket.AF_INET6, "ipv6")):
        targets = [a for a in answers if a[0] == family]
        if not targets:
            report["steps"][name] = {"ok": False, "reason": "no DNS address"}
            continue
        try:
            started = time.monotonic()
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect(targets[0][4])
                with context.wrap_socket(sock, server_hostname=HOST) as tls:
                    cert = tls.getpeercert()
                    report["steps"][name] = {"ok": True, "tls": tls.version(),
                        "cipher": tls.cipher()[0], "elapsed_ms": round((time.monotonic()-started)*1000),
                        "certificate_subject": str(cert.get("subject")), "issuer": str(cert.get("issuer")),
                        "not_after": cert.get("notAfter")}
        except (OSError, ssl.SSLError, TimeoutError) as exc:
            report["steps"][name] = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}
    try:
        started = time.monotonic()
        request = urllib.request.Request(URL, headers={"User-Agent": "MetaAnalyse-TLS-Verification/1.0"}, method="GET")
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            payload = response.read(65536)
            parsed = json.loads(payload)
            report["steps"]["https"] = {"ok": response.status == 200 and parsed.get("retCode") == 0,
                "status": response.status, "retCode": parsed.get("retCode"),
                "elapsed_ms": round((time.monotonic()-started)*1000),
                "via_proxy_possible": any(report["proxy_environment_present"].values())}
    except (OSError, ValueError, urllib.error.URLError, TimeoutError) as exc:
        report["steps"]["https"] = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--output", default="rest-tls-windows-evidence.json")
    args = parser.parse_args()
    result = run(args.timeout)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
    print("Evidence:", args.output)
    print("Results:", {key: value.get("ok") for key, value in result["steps"].items()})
    return 0 if result["steps"].get("https", {}).get("ok") else 1

if __name__ == "__main__":
    raise SystemExit(main())
