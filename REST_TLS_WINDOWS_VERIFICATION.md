# REST TLS Windows verification — 2026-10-20

## Scope and evidence

Issue #11 and isolated Draft PR #12 candidate `13901274dac527f0aacfaf48481414b0971d6012` were reviewed. The auditor reported a successful public GET `/v5/market/time` with HTTP 200, TLS 1.3, `retCode=0`, and certificate validation. This does **not** identify the cause of the earlier TLS failure. The separate Windows 11 Pro host has **not** been tested. Do not infer production readiness from green CI.

## Implementation observations

- `src/meta_analyse/exchange.py`: `BybitPublic` uses `ManagedAsyncClient(base_url=..., timeout=20)`; up to four attempts, backoffs 1/2/4 seconds. Thus one call may consume approximately 87 seconds before final failure. Cancellation propagates because `CancelledError` is not caught by the retry loop. Retry policy currently catches broad HTTP errors and RuntimeError, including certificate verification failures and non-transient HTTP errors: classify retryable failures separately before considering this production-ready.
- `src/meta_analyse/http_client.py`: cancellation cleanup uses an HTTPX/httpcore trace extension to close partially connected streams. Verify behavior with pinned HTTPX/httpcore versions; the trace event names are implementation-sensitive. No explicit SSLContext is passed by `BybitPublic`; default HTTPX certificate behavior, certifi trust, and environment-based proxy/trust configuration must be captured on the target. Do not disable hostname or certificate verification.
- Direct socket TLS and HTTPS requests may use **different routes**: the diagnostic socket connects directly to resolved IPs, whereas urllib HTTPS can honor proxy environment. Their results are intentionally separate; a direct failure does not prove an application failure behind a proxy.

## Independent Windows 11 Pro runbook

From an isolated, reviewed checkout (Python 3.12), without credentials or production DB access:

```powershell
py -3.12 --version
Get-ComputerInfo | Select-Object WindowsProductName,WindowsVersion,OsBuildNumber
Get-Command py
Get-ChildItem Env:*PROXY* | Select-Object Name
py -3.12 scripts/verify_rest_tls_windows.py --timeout 8 --output rest-tls-windows-evidence.json
```

Do not publish full proxy URLs (may contain credentials), usernames, local IPs, or complete environment dumps. Diagnostic JSON reports presence of proxy variables, not their values. Review the JSON before sharing. The script requires no API keys, performs only a public GET and read-only DNS/TLS checks, and does not connect to PostgreSQL.

Check `ipv4`, `ipv6`, `https` separately. IPv6 absence is not automatically a failure. A successful TLS handshake on direct IPv4/IPv6 does not validate an HTTPS proxy path. Compare Python default trust store with the actual HTTPX/certifi trust context on the target; record `python -m pip show httpx httpcore certifi` separately.

## Negative tests and acceptance

Required isolated, deterministic fault tests (mock/loopback, never external invalid TLS endpoints): untrusted CA, wrong hostname, handshake abort, DNS lookup failure, unreachable proxy, connect/read timeout, cancellation during handshake, and repeated concurrent cancellations. Assert no insecure retry fallback, bounded completion, no leaked socket, no Qt event-loop blocking, and no trading method. Keep all tests fail-closed.

Do not call this verified until: negative tests and exact-SHA Windows/Linux CI pass, and operator-provided target-host logs demonstrate the same checks. Record host OS/build, Python version, HTTPX/httpcore/certifi versions, proxy presence, trust context, timestamp, exact SHA, DNS family, TLS version, certificate issuer and HTTP status. A single GET 200 is not a historical root-cause analysis.

## Current decision

**NO-GO** for separate Windows live-data commissioning. No target-host execution, merge, deployment, production database change, or orders were performed in this work.
