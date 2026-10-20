# Runtime test matrix — 2026-10-20

Tested code SHA: **13901274dac527f0aacfaf48481414b0971d6012**. Report-only commits after this SHA do not change the tested source. Overall NO-GO for real commissioning acceptance.

| Environment | Full pytest | PostgreSQL | Mandatory storage cases | Repeated lifecycle |
|---|---|---|---|---|
| Local Windows11, Python3.12.15, Qt6.12 offscreen | 625 passed, zero skipped | 17.6, disposable lab DB | 10/10 | 10 × 67 passed, zero skipped |
| GitHub Windows Server2025, Python3.12.10, Qt6.12 offscreen | 625 passed, zero skipped | 17.11, disposable cluster | 10/10 | 10 × 67 passed, zero skipped |
| GitHub Linux, Python3.12.15 | 624 passed, one Windows installer skip | 17, service | 10/10 | 10 × 67 passed, zero skipped |
| GitHub Linux, Python3.12.15 | 624 passed, same Windows-only skip | 18.6 (server_version180006) | 10/10 | 10 × 67 passed, zero skipped |

CI: https://github.com/YehorBabenko88/meta_analyse/actions/runs/39437122411 and https://github.com/YehorBabenko88/meta_analyse/actions/runs/39437122173. Both successful run records pin the tested SHA. Downloaded JUnit was independently parsed: no missing required case, failure/error or unexpected skip; every repeat contains exactly 67 passing testcases. This is 40 fresh lifecycle processes / 2680 testcase passes, not 2680 physical connect/disconnect cycles.

| Negative / supplemental check | Result |
|---|---|
| Extreme Decimal import/audit values including ±0e999999999 | Six bounded subprocess cases pass; zero audit cases failed before fix |
| Independent commissioning fault/security module | 17 passed, included in full suite |
| PostgreSQL concurrent distinct/identical imports | Both fail on first candidate, pass after native bounded serialization |
| Occupied actual-NUL advisory key | Timeout without source mutation; retry after release succeeds |
| Original failure plus cleanup/unlock failure | Original failure retained |
| Monitor initialization and collector DB write during close | Close waits actual thread completion |
| Book reconnect with increasing pre-snapshot delta | Delta rejected, fresh snapshot required; no stale levels |
| Invalid book delta, then healthy deltas without disconnect | Fail-closed, no autonomous recovery: remaining NO-GO |
| TLS current-host application public GET | HTTP200, retCode0, TLS1.3, certificate/hostname verification |
| PowerShell syntax / Python compilation / 198 extracted source hashes | PASS; no target package execution |

Synthetic Qt20-instrument / 20,000 events/s benchmark at tested SHA: Windows CI ~19,991 events/s, render p95 3.469ms, heartbeat p95 12.681ms, close event 2.123ms; Linux ~19,994 events/s, render p95 4.376ms, heartbeat p95 12.908ms. Both worker_stopped=true and loop_closed=true. These 3-second callback/offscreen tests exclude network, SQL persistence, exchange parsing and microstructure calculations; they are not soak or end-to-end throughput certification.

| Real target gate | Status |
|---|---|
| Prior 9d1bfff5… / 586 tests / reported670 lifecycle results | UNVERIFIED: source and logs unavailable |
| Separate Windows11 Pro / Python3.12 / PostgreSQL18 / installed MetaScalp | NOT RUN |
| Target TLS and network outage/recovery | NOT RUN |
| 30-minute smoke | NOT RUN |
| 2-hour soak | NOT RUN |
| 24-hour stability | NOT RUN |
| Queue depth, dropped-event and market completeness reconciliation | NULL / UNVERIFIED |

Automated Windows PostgreSQL17 is not evidence of Windows PostgreSQL18 target compatibility. Successful Linux18 does not close that hardware gate.
