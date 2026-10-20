## LS5 adaptation update — 2026-10-20

Tested source: `5928b4e3aadac55d64bdd013c83ed698cfd8d838`. Draft PR #12. **Actual LS5: NO-GO for 30min; NO-GO for 2h and 24h. All timed trials NOT RUN.** The earlier conditional admission applied to a cleared isolated host and does not authorize this LS5.

[Exact-source Windows/Linux CI](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39480839261): Windows698 passed, zero skips; Linux697 passed, one expected Windows installer skip. [Additional PG18 CI](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39480839300):697 passed, same expected skip. Every job recorded10 fresh-process lifecycle batches of67 passes. Local focused host/commissioning regressions:65 passed. Raw JUnit/source provenance and safe host counts: `docs/ls5_commissioning_evidence/`. These are new reproducible results, not validation of historical586/670 claims.

Host authorization now requires DPAPI-bound multi-identifier HMAC identity, explicit operator approval, complete fresh Grid/environment checks, exact source and manifest digest, isolated PG18 listener/data directory and minimal role, approved signed MetaScalp API owner, mandatory TLS verification. No bypass flag. See `LS5_HOST_IDENTITY_REPORT.md`, `LS5_POSTGRES_PREFLIGHT.md` and `WINDOWS_COMMISSIONING_PLAN.md` for evidence and operator commands.

Current blockers: Grid deployment directories and incomplete process-path coverage; existing PostgreSQL18.6 listens on55432 wildcard addresses with role/isolation unverified; signed MetaScalp files exist but no active API. No enrollment authorization, separate cluster/role, application run, service stop or existing database changes were made.

Residual limitations: bounded scans cannot prove absence of renamed custom agents; real cross-machine DPAPI test not performed; fresh OS scans before terminal requests may add latency (up to collector timeout), not covered by synthetic UI benchmark;30min timer requests normal shutdown rather than imposing a hard exit. Never claim duration/reconciliation success without real host logs.

---

## Historical commissioning record (superseded for LS5 admission)

# Runtime matrix â€” 2026-10-20 re-audit

Tested code **446c72bd97cacc31f9937c9ab941d11539733be4**. Later report-only commits are distinguished from tested source.

| Environment | Full pytest | PostgreSQL | Mandatory PG/shutdown | Lifecycle |
|---|---|---|---|---|
| Windows CI Server2025/Python3.12.10/Qt6.12 offscreen |651 passed,0 skipped|18.6|11/11+5/5|10x67 PASS,0 skipped|
| Linux CI/Python3.12.15 |650 passed,1expected Windows installer skip|18.6|11/11+5/5|10x67 PASS,0 skipped|
| Additional Linux18 workflow |650 passed,1same expected skip|18.6|11/11+5/5|10x67 PASS,0 skipped|
| Supplementary local Windows11/Python3.12.15 |651 passed,0 skipped|17.6 lab only|11/11+5/5|10x67 PASS,0 skipped|

Exact push CI: https://github.com/YehorBabenko88/meta_analyse/actions/runs/39446586945 and https://github.com/YehorBabenko88/meta_analyse/actions/runs/39446586928 . All651 identities unique; required module.test cases, source SHA, actual server versions and every lifecycle XML independently checked. Linux only skips test_failed_pip_install_never_reports_success_or_creates_launcher. No mandatory PG/shutdown skips. Separate immutable PR6 contract8 PASS at091e9db is additional source evidence.

| Independent fault/probe | Result |
|---|---|
| Invalid/nonfinite delta; sequence/update regression | New epoch/socket; trailing old delta not published; fresh snapshot required |
| Increasing delta immediately after reconnect | Rejected until snapshot |
| Silent feed; continuous unrelated traffic | Per-symbol watchdog reconnects |
| Real loopback WebSocket,4scenarios | Both sockets close; only snapshots1and10 publish; UNVERIFIED gap |
| Retained snapshot | Immutable across mutation/recovery |
| Failed-handshake backoff |0.1,0.2,0.4,0.4,0.4 deterministic jitter; stop/cancel interrupts active30s wait |
| Real verified TLS | Untrusted/wrong-host rejected, valid localhost accepted, timeout/cancel/abort cleanup |
| Audit-host public app REST | GET200/retCode0/TLS1.3; no target implication |
| Extreme Decimal import/audit | Six bounded cases includingÂ±0e999999999 |
| Real advisory contention | Server wait observed, then release/resume; stuck holder times out before source mutation |
| Cleanup cancellation | Red masking reproduced; final original-error preservation passes |
| JUnit unrelated/module-collision/skipped-required | Final gate rejects |
| Rejected d3856c7 | Windows639 PASS/11skip despite green icon; not accepted |

Synthetic20-symbol/20k-events/s: Windows~19994events/s, render p95=2.730ms, heartbeat p95=12.631ms, close=1.743ms. Linux~19997events/s, render p95=4.673ms, heartbeat p95=12.984ms. Worker stopped/loop closed. Three-second offscreen callback benchmark excludes network/SQL/parsing/microstructure; not real-PC or soak evidence.

| Target stage | Admission | Execution |
|---|---|---|
| Separate Windows11 Pro/Python3.12/PG18/MetaScalp preflight | Mandatory before activation | NOT RUN |
| Supervised30-minute read-only smoke | CONDITIONAL GO after approved target preflight/logging | NOT RUN; no PASS |
|2-hour soak|NO-GO pending reviewed30m logs and telemetry|NOT RUN|
|24-hour stress|NO-GO pending reviewed2h/resource/reconciliation proof|NOT RUN|
|Queue/drop reconciliation|Unknown; blocks longer-stage promotion|NULL/UNVERIFIED|
|Original586/9d1bfff5 claims|Not used as evidence|UNVERIFIED|

Raw evidence/SUMMARY.json: docs/commissioning_evidence_v3. Baseline13901274 evidence remains in docs/commissioning_evidence. CI/offscreen timings do not replace target logs.
