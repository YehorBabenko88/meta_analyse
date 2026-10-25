# PR #47 — независимая приёмка PostgreSQL 18.1

Дата 2026-10-25. Frozen HEAD `59626930a911c0dde330f7760c78ccd99468a1f4`.
G0 FAIL_CLOSED, G1 BLOCKED, ADMINIT NO-GO.

## Проверенный код

- `pg_cluster_attestation.py`: read-only transaction, `pg_catalog` search_path, exact version 180001, loopback 127.0.0.1:55480, database/role/owner/role flags, no role membership, no CONNECT elsewhere, system_identifier.
- `pg_authorized_connection.py`: opt-in gate and PG* environment refusal; no evidence that every generic Store/Window caller is wrapped.
- `pg_cluster_plan.py`: pure PlanOnly; rejects 5432 and path collisions in caller-supplied list. Does not inspect filesystem/reparse handles.
- `pg_checkpoint_witness.py`: read-only WAL/checkpoint observations, no durability certificate. OBSERVED cannot establish recovery after physical crash without independent restart evidence.
- `commissioning/initialize-private-schema.py`: uses authorized_private_connection before SCHEMA DDL, but expected identifier is CLI `--cluster-system-identifier`, not independently verified G1 receipt.
- `commissioning/preflight.py`: uses authorized_private_connection for its DB inspection; other commissioning Store/Window write call sites require a complete call-graph audit.
- `commissioning/prepare-private-cluster.ps1`: host/enrollment guards, new path check, loopback and 55480, exact binary 18.1, SCRAM; however it performs initdb/start/CREATE ROLE/CREATE DATABASE before any independent system_identifier receipt check. Port listener probe closes before bind; path checks are susceptible to replacement.
- `commissioning/create-test-db.sql`: checks database/port/version/data_directory/user/listen_addresses but no independent system_identifier. SQL relies on unqualified catalog functions and lacks explicit trusted search_path.

## Critical blockers

**P0-A: circular expected system_identifier.** `initialize-private-schema.py` and preflight accept a command-line expected value. An operator reading the value from the same endpoint under test does not provide independent provenance. G1 must bind a trusted, separately approved cluster receipt (source, owner, PGDATA, PID/start time, version, identifier) before schema DDL.

**P0-B: role permission contradiction.** Attestation invokes `pg_catalog.pg_control_system()`, which may require elevated monitoring permissions. The policy forbids any role membership, including monitoring roles. Real PostgreSQL 18.1 must prove whether the dedicated non-superuser can execute this function. A fake row is insufficient; on permission denied the correct behavior is BLOCKED. Do not weaken the role or grant broad privileges without separate security review.

**P1-C: initialization identity/TOCTOU.** Port availability and path ancestry are checked before initdb, without stable file handles/ownership evidence across creation/start. No safe automatic rollback should touch any directory unless exact owned PGDATA is reattested.

**P1-D: incomplete caller coverage.** `Store.connect()` remains a generic connection path; evidence is insufficient to claim every commissioning DDL/DML caller is gated. Need exhaustive call graph and deny-before-write tests.

**P1-E: real SQL/server compatibility.** Hosted PR #47 synthetic run 40203574132 QUEUED at inspection; full CI 40203574154 and storage 40203574138 SKIPPED. No disposable PG18.1 evidence on frozen HEAD. Fake database tests do not establish function privileges, catalog SQL correctness or checkpoint semantics.

**P2:** long-run disk-full, crash/COPY, repeated cancellation, concurrent import, orphan writer and 30m/2h/24h gates remain unverified for physical cluster.

## RED / GREEN / BLOCKED matrix

| Control | Status |
|---|---|
| Source identity, SHA | PASS (GitHub HEAD checked) |
| SQL function/role permissions on real PG18.1 | BLOCKED |
| Expected system_identifier independent provenance | FAIL |
| Preflight/schema use opt-in gate | SOURCE PASS |
| All Store/Window caller coverage | BLOCKED |
| Port 5432 avoidance in planned paths | SOURCE PASS |
| Physical PGDATA/reparse/TOCTOU | BLOCKED |
| Advisory locks and checkpoint atomicity | Earlier code reviewed; exact integrated runtime BLOCKED |
| Read-only witness | SOURCE PASS, durability proof BLOCKED |
| Synthetic CI exact HEAD | QUEUED at inspection |
| Disposable PostgreSQL 18.1 exact HEAD | NOT RUN |
| G0 / G1 | FAIL_CLOSED / NOT AUTHORIZED |

## Required disposable PG18.1 matrix

1. New isolated container/runner only; assert version_num=180001, fresh `system_identifier` and no production DSN.
2. Execute attestation as dedicated non-superuser with no role memberships; record function privilege outcome without exposing credentials.
3. Negative wrong identifier, database, role, 5432, hostaddr, PG* env, unexpected grants and role flags; no DDL/DML after refusal.
4. Test `pg_control_system()` and `pg_control_checkpoint()` permissions, search_path shadowing, SQL syntax and no role elevation.
5. Crash at COPY, before checkpoint update, after commit; verify restart rows/checkpoint and no duplicates.
6. Concurrent same-symbol imports, lock_timeout, cancellation during commit/rollback, shutdown drain.
7. Test PlanOnly symlink/junction/path replacement and ownership-safe rollback in disposable Windows filesystem.
8. Require exact SHA/tree/run/attempt, complete JUnit identities, no unexpected skips and privacy-projected artifacts.

## Rollback

Only after independent confirmation of the NEW cluster's identifier, PID/start time, owner, executable and exact PGDATA may an operator stop that specific process. On any mismatch: STOP, no `pg_ctl`, DROP, directory removal or service changes. Preserve partial new PGDATA for forensic review; deletion needs separate approval. Existing 5432 must never be targeted.

**Verdict: PR #47 PostgreSQL G1 NO-GO.** No physical host, production DB, merge, deployment or G1 operations performed.

## Follow-up 2026-10-25: exact CI and test-scope correction

PR #47 HEAD `59626930a911c0dde330f7760c78ccd99468a1f4` unchanged: synthetic 40203574132 QUEUED, full CI 40203574154 SKIPPED, storage 40203574138 SKIPPED. PR #49 HEAD before this documentation update `d81e70aab4ebfd5f46add051877cc8223f0abf54`: CI 40204950133 QUEUED, ADMINIT synthetic 40204950126 SKIPPED. Newly added `tests/test_pr47_pg_source_contract.py` only checks source text; its presence does not prove execution or database compatibility. No new server-side SQL privilege evidence exists. G1 remains NO-GO.
