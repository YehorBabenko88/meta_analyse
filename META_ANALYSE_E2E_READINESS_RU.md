# MetaAnalyse E2E readiness — independent CI boundary review (2026-10-26)

**Decision: ADMINIT NO-GO; G0/G1 BLOCKED.** Read-only source and hosted log review. No physical ADMINIT, public Bybit network, production PostgreSQL, trading credentials or orders.

## Exact sources

- PR #47 HEAD: `59626930a911c0dde330f7760c78ccd99468a1f4`.
- PR #50 HEAD reviewed: `35073498ca094a1036c083b77b80f46364763758`.
- CI [40205217917](https://github.com/YehorBabenko88/meta_analyse/actions/runs/40205217917): Linux FAILURE (2311 PASS / 3 FAIL / 1 SKIP); Windows FAILURE (2308 PASS / 7 FAIL / 1 ERROR); archive pinned contract SUCCESS.
- PR #47 [40203574132](https://github.com/YehorBabenko88/meta_analyse/actions/runs/40203574132): synthetic FAILURE; other workflow SKIPPED is not PASS.

## Confirmed P0/P1 findings

**P0 — Synthetic-only tripwire not installed in general CI.**
`tests/test_final_integration_workflow.py` asserts `psycopg.connect` and `subprocess.Popen` raise `SYNTHETIC_ONLY_BOUNDARY`. Those calls are intercepted by the autouse fixture in `scripts/integration_synthetic_boundary.py` **only when the pytest plugin is loaded**. The general CI runs all tests without that plugin; on Linux it tries a malformed DSN and an unavailable powershell executable, and on Windows it may spawn a child. This is not a legitimate safety boundary. Fix ownership: scope the tests to the synthetic workflow, or explicitly activate the fixture only for the isolated test subset; do not disable safety tests or weaken them to SKIP. The synthetic workflow uses `--noconftest -p scripts.integration_synthetic_boundary` and has its own JUnit/source binding.

**P1 — Frozen Git object missing from general CI.**
`tests/test_native_scm_adapter.py::test_shared_predicate_refactor_is_equivalent_to_frozen_pr39` invokes `git show 4a92643c00a7e4d113025e1df427d8f4850f0981:commissioning/process_identity.py`. General checkout does not fetch the object. Synthetic workflow explicitly fetches that SHA. Require pinned source availability before invoking the test; no silent fallback to HEAD.

**P1 — Windows PG attestation / cleanup.**
Windows CI reports `PG_ENVIRONMENT_FORBIDDEN` in commissioning tests, and an unraisable Popen teardown error. Do not classify these as PASS; reproduce with a disposable PG18 cluster and verify subprocess ownership and cleanup.

**P0 — Transport-only evidence is not FULL_E2E_PASS.**
`scripts/public_bybit_e2e_probe.py` is transport-only, with thread/task resource counters. It cannot prove PostgreSQL commit/readback, Qt freshness, RSS/CPU/disk/queue occupancy or forced overflow. Do not promote `TRANSPORT_PASS` to G2.

## Architecture and E2E contract matrix

| Producer → consumer | Invariant | Evidence status |
|---|---|---|
| Public Bybit REST/WS → OrderBookStream | Snapshot required per connection epoch; delta regression invalidates | Synthetic proof only; real depth50 loss unproven |
| OrderBookStream → MarketCollector | Immutable snapshot; no publication after invalidation | Synthetic proof; slow-consumer overflow detection incomplete |
| MarketCollector → PostgreSQL | Commit-before-telemetry; failure blocks UI publication | Fake DB fault injection in PR #50; real PG18 readback missing |
| RawTradeStream → RawPipeline | Idempotent execution key, gap invalidation | Local integration; exchange completeness unproven |
| Archive → receipt → DB/checkpoint | Atomic batch and recoverable checkpoint | Crash-at-checkpoint physical witness missing |
| PostgreSQL → DesktopService → Qt | UTC/Decimal/immutable DTO, stale UNVERIFIED | Real Qt/DB witness missing |
| Shutdown → worker/DB | Drain active to_thread before close success | Synthetic tests; unbounded DB I/O remains BLOCKED |

## Offline E2E fault-injection and required resource telemetry

Synthetic suite must test invalid delta → reconnect → fresh snapshot, duplicate/out-of-order, silent socket, slow consumer, queue overflow → INVALID, cancellation during SQL write, rollback and stale UI status. Test a real bounded queue rather than only a toy `asyncio.Queue`. No physical execution until G1.

Before G2, instrument per-symbol snapshot epoch and message age, transport/application queue occupancy and overflow count, RSS peak and trend, CPU time, disk free/DB/WAL growth, UI p95/p99 event-loop latency, SQL commit/readback and shutdown ownership. Any unavailable required metric = BLOCKED, never PASS.

## Staged G2–G5 runbook

| Gate | Preconditions | PASS criteria | Immediate STOP / FAIL | Evidence / rollback |
|---|---|---|---|---|
| G2 short smoke | G0/G1 accepted, exact SHA/tree, disposable PG18, public read-only Bybit, no keys | Fresh snapshot for every symbol, 0 false VALID, 0 unexplained SQL gaps, Qt responsiveness p95 <100ms | Any private endpoint/order attempt, stale CURRENT, missing commit, unknown SHA | Epoch/sequence timeline, SQL rows, Qt timings, redacted config; stop producers and drain |
| G3 30m | G2 PASS and separate approval | 0 false VERIFIED; all required metrics present; bounded queue/memory | Queue overflow without invalidation, UI freeze, DB mismatch | 30m samples, JUnit, artifact hashes; graceful shutdown |
| G4 2h | G3 PASS and separate approval | Reconnect requires fresh snapshot; no orphan writes; stable RSS/CPU/disk trend | Reconnect loop, stuck SQL, missing recovery | 2h metrics, crash/rollback witness, operator approval |
| G5 24h | G4 PASS and separate approval | Restart/retention/disk-pressure safe; 0 integrity mismatch | Disk exhaustion, leaks, stale VALID | 24h resource ledger, retention receipts, verified shutdown |

Budgets are provisional; G2 must freeze numeric limits for CPU, RSS, disk, queue and DB growth based on actual ADMINIT resources. No implicit automatic promotion between gates.

**Next owners:** CI boundary and frozen-object checkout; PostgreSQL18/SCM attestation; orderbook real overflow instrumentation; Qt health witness. **NO-GO** until independent exact-SHA CI and full E2E evidence.
