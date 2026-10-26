# POSTGRES_PR52_55_FINAL_ACCEPTANCE_RU

Дата: 2026-10-26. Независимый аудит, физический ADMINIT не использовался.

## Exact-source inventory

- PR #52 HEAD `8a1c20184cbd878097f62530fc07630568fb7f84`, tree по авторскому evidence `334df27319ce37fe562b6195b255742dae6db8c8`.
- PR #53 HEAD `bbbc1cc75f9bb15490867227396267ba81eaf9b0`.
- PR #54 HEAD `0883a979ba364a778a3ca78d0dc4fdc5026e46d7`, заявленный tree `b10b07c888e8fd3e95c97ed5945479cde7196b5a`.
- PR #55 HEAD `edc8e831c202e3597e27532359ab9c47a9f29a88`, заявленный tree `84e128ca44e2ffe54bda7c003d0358a0b8d8b8fd`.
- Tree values above are PR-authored evidence, not independently recalculated git object hashes in this review.

## Real hosted results

PR #52 exact PR run 40295979565: synthetic Windows and Linux SUCCESS; dependent disposable-postgres18 job 121482616197 SUCCESS, log says `collected=4 skipped=0 failed=0`. Source SHA verified. PR description reports push run 40295973256 SUCCESS with independently inspected ZIP evidence, but this review did not re-download ZIPs.

PR #53 exact CI run 40301079889: Windows job 121498837331 FAIL, Linux 121498837452 FAIL, archive-pinned-contract SUCCESS. Linux actually ran PostgreSQL **18.1**, verified version 180001, 10 x 67 lifecycle PASS, 8 archive PASS, then full suite **4 failed / 2389 passed / 5 skipped**. Windows used PG **18.6**, 10 x 67 lifecycle PASS, full suite **4 failed / 2390 passed / 4 skipped / 1 error**.

Confirmed full-suite failures are synthetic-boundary and source-fixture failures, **not SQL/server errors**:
1. `test_final_active_boundary_denies_live_database`: psycopg parsed `synthetic-never-connected`, raising ProgrammingError instead of synthetic AssertionError; boundary plugin was not active in full CI.
2. `test_final_active_boundary_denies_native_child`: Windows child did not raise, Linux lacked powershell.exe; boundary plugin not active.
3. `test_final_http_boundary_rejects_external_request_before_dns`: expected synthetic refusal absent.
4. `test_shared_predicate_refactor_is_equivalent_to_frozen_pr39`: frozen git object `4a92643c...` unavailable in checkout.
5. Windows teardown `PytestUnraisableExceptionWarning` from Popen after the unexpected child attempt.

These tests must run only with explicitly installed synthetic-boundary plugin and guaranteed source fixture, or be separated from full CI with an independently mandatory synthetic job. Do not skip mandatory negative assertions silently. Fix by owning CI integrator; no change to production PostgreSQL justified by these failures.

## PostgreSQL source boundaries

- `pg_cluster_attestation.py`: exact PG18.1, localhost/55480, role/database ownership, no dangerous role flags, memberships or CONNECT elsewhere, pg_catalog-qualified `pg_control_system()`, fixed refusal.
- `pg_authorized_connection.py`: PG* env guard, connection-parameter allowlist and opt-in attestation. Generic `Store.connect` is not automatically covered.
- `pg_checkpoint_witness.py`: read-only observation of WAL flush/checkpoint and orderbook row. `OBSERVED` is not crash-durability proof or authenticated physical G1.
- `prepare-private-cluster.ps1`: exact Windows/host, enrollment, path and port checks before new initdb; port/path replacement TOCTOU remains. Never use against existing 5432.
- `initialize-private-schema.py`: authorized connection precedes schema DDL; expected system identifier is supplied by CLI and requires independent G1 receipt provenance.
- Real least-privilege `pg_control_system()` and `pg_control_checkpoint()` permissions on PG18.1 with zero memberships remain unverified by the four hosted disposable cases.

## New deterministic RED/GREEN coverage

`tests/test_pg_attestation_fault_injection.py`: simulated failures at each of three attestation SQL stages and seven identity mismatches must close connection and never expose it for DDL/DML; positive case checks query order. These are synthetic tests, **not** real SQL compatibility or crash recovery. New exact-SHA hosted results pending.

## Required disposable PostgreSQL 18.1 matrix

- Real SQL catalog function permissions with non-superuser/no memberships and denied access to other DBs.
- Independently approved expected system_identifier, not echoed from tested DSN.
- Wrong port/hostaddr/role/database/version/identifier, PG* inherited variables, search_path shadowing, deny-before-write.
- Concurrent import same/different source, advisory lock timeout, COPY+checkpoint atomicity.
- Crash at pre-COPY/mid-COPY/pre-checkpoint/post-commit, restart dedup/checkpoint consistency.
- Repeated cancellation and executor drain until commit/rollback; no orphan writer.
- Disk-full, max_connections, WAL budget and ownership-safe rollback on isolated new PGDATA.
- Exact SHA/tree/run/attempt/job, JUnit identities, no unexpected skips, privacy-safe artifacts.

## P0 / P1 / P2

**P0:** Physical G0 FAIL_CLOSED; no independent G1 cluster receipt, no full caller coverage or physical ownership proof. ADMINIT G1 NO-GO.

**P1:** SQL privileges for pg_control functions and independent identifier origin unproven; full CI synthetic-boundary failures need correct isolation; crash/restart/rollback not qualified.

**P2:** Resource budgets, 30m/2h/24h and long-running orderbook liveness remain future operator-controlled gates.

## Decision

**Source review PARTIAL; PR52 hosted synthetic + disposable PG18.1 PASS (four cases only); PR53 full CI FAIL (synthetic fixture failures); PR54/55 hosted qualification PENDING/other job failures not transferred; physical G0/G1 NO-GO.**

No production DB, ADMINIT cluster, merge, deployment, rerun or commissioning performed.
