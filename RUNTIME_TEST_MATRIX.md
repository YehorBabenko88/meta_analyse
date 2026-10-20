# Runtime test matrix — 2026-10-20

| Gate | Source evidence | Current status |
|---|---|---|
| Prior 9d1bfff5… /586 tests | Candidate/logs unavailable, user will provide later | UNVERIFIED |
| TLS/security | App public REST GET200/retCode0/TLS1.3, cert+hostname verification enabled; current audit environment only | CONDITIONAL GO |
| Archive validation stall | 1e-999999999 stalls baseline; reviewed bounded conversions and subprocess regression | Candidate CI pending |
| PostgreSQL contention | Correct actual NUL advisory key, no partial source on contention, retry after release | Local PASS, candidate CI pending |
| Orderbook state/recovery | Malformed IDs/NaN/partial delta rejection + fresh-snapshot injected transport reconnect | Local PASS, candidate CI pending |
| Shutdown/write drain | Raw/market/schema writes wait commit/rollback despite repeated cancel | Local PASS, candidate CI pending |
| Windows automated full suite | Exact candidate SHA required, ten PostgreSQL cases, no unexpected skips | PENDING |
| Linux automated full suite | Exact candidate SHA; PostgreSQL18 job and PostgreSQL17 compatibility job | PENDING |
| Lifecycle | Ten fresh processes, EXACT67 passed/case manifest, zero skipped | PENDING |
| Separate Windows11 Pro + Python3.12 + PG18 + MetaScalp preflight | Target logs unavailable | NOT RUN / NO-GO for activation |
| 30-minute hardware smoke | No real target logs | NOT RUN |
| 2-hour hardware soak | No real target logs | NOT RUN |
| 24-hour hardware stability | No real target logs | NOT RUN |

The runtime launcher records persisted ages/gaps and GUI timer jitter, and the observer records CPU, memory, handles, threads. Queue depth, dropped-event reconciliation and true market completeness must not be inferred from those counters. NULL/UNVERIFIED cannot satisfy their acceptance gates.
