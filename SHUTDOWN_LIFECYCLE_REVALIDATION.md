# Shutdown lifecycle revalidation — 2026-10-20

## Scope and provenance
- Working branch: `parallel/integration-ci-gates-20261019` (Draft PR #9).
- Reviewed PR #12 candidate: `13901274dac527f0aacfaf48481414b0971d6012`.
- GitHub candidate workflows: CI #1090 (`39437432965`) SUCCESS; Storage integration #188 (`39437433136`) SUCCESS.
- Compared contents of `src/meta_analyse/write_drain.py`, `src/meta_analyse/market_collector.py`, and `tests/test_integration_contract_shutdown.py` on candidate and PR #9: identical blobs.

## Verified by source inspection
- `drain_thread_write` creates a tracked task around `asyncio.to_thread`, shields it across cancellation, and waits until it completes before propagating cancellation; errors after cancellation are retrieved and logged.
- `MarketCollector._book`, open-interest writes and schema initialization call `drain_thread_write`. `stop()` cancels and gathers collector tasks.
- Synthetic tests cover delayed commit, repeated cancellation, delayed rollback/error logging, ordinary failure propagation and success.
- These tests support a *coroutine lifetime* claim, not a claim that an unfinished DB write was observed after actual process exit. Such an occurrence has NOT been proven.

## Open verification gaps / blockers
1. The `archive-contract` CI job checks out the moving `parallel/archive-reliability` branch. Its tested source is not pinned to the triggering PR's SHA. Record both SHAs or use immutable dependency SHA for reproducible exact-SHA evidence.
2. Linux CI uses PostgreSQL `17.6` service; PostgreSQL 18 is not proven by this workflow. Check Windows PostgreSQL version and add explicit PG18 evidence.
3. JUnit `--require-exact` matches bare testcase names and checks required skip, but does not bind to expected module classname. Namesakes in another module can satisfy the requirement. Enforce full classname + testcase identity and a negative collision test.
4. No verified actual Windows runtime shutdown while CSV import, archive validation, schema initialization, reconnect and PostgreSQL commit are all fault-injected. Do not claim these scenarios passed.
5. No new independent execution of 10 lifecycle cycles in this review; the workflow is configured for 10 Linux repeats, but per-cycle evidence was not independently inspected.
6. The code review did not exhaustively verify Qt closeEvent ownership, all executor call sites, lock release ordering or connection closure. Those require instrumented cross-module tests.
7. A finite timeout cannot truthfully declare successful shutdown while a DB thread remains active. If an operation hangs, report shutdown as incomplete and retain ownership rather than close its connection.

## Gate to Windows live-data commissioning
NO-GO until the missing PG18/exact-SHA evidence, mandatory JUnit identity checks, and real Windows fault-injection/lifecycle tests are complete. No merge, deployment, production DB mutation or real orders were performed.
