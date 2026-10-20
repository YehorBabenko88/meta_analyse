# Blockers and remediation — 2026-10-20

Initial overall verdict: NO-GO. Baseline 9d1bfff5…/586/670 was reported, not supplied.

| Blocker | Independent baseline result | Reviewed remediation | Provisional verdict |
|---|---|---|---|
| REST TLS failure | Not reproducible now: verified Bybit GET200 with TLS1.3 using app/certifi and Windows trust contexts | No CA/trust changes or verification bypass justified. Capture exact exception chain and CA/proxy presence if target fails | CONDITIONAL GO in current environment; target UNVERIFIED |
| Archive validation stall | Both auditor/importer exceed2s for Decimal1e-999999999 | PR6 bounded exponent + PR8 digit count conversion; SQL120s statement/15s lock bound and immediate contended advisory-lock failure | Pending full candidate CI |
| Orderbook recovery | Baseline accepts malformed IDs/infinite sizes/delta u=1 and may leave partial mutated valid book | PR7 strict integer IDs, finite levels, clear on malformed partial mutation; independent transport reconnect test | Pending full candidate CI |
| Unfinished writes after stop | Baseline collector.stop and service.close can finish while executor writes/schema initialization remain active | PR9 owned drain helper + additional monitor-schema drain discovered by independent audit | Pending full candidate CI; actual final window already waits executor and must not be described as proven post-process writes |
| Agent contention regression itself | New test used literal backslash-zero, not production NUL key; failed on real PostgreSQL | Corrected test key in isolated candidate; mandatory gate strengthened to ten cases | Local PASS |
| Separate target commissioning | No target access/logs | Package, explicit approved operator preflight, then30m/2h/24h stages | NO-GO until actual logs |

No trading credential, production DB, main branch, deployment or merge is involved. Read-only package launcher denies HTTP writes; automated tests use mocks/loopback and disposable databases.
