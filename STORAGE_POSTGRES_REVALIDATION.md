# STORAGE_POSTGRES_REVALIDATION

Date: 2026-10-20
Scope: Draft PR #8, branch `parallel/storage-ingestion`; comparison with PR #12 candidate `13901274dac527f0aacfaf48481414b0971d6012`.

## Findings and remediation
- Candidate and PR #8 retain exact Decimal coefficient/exponent to integer microseconds, bypassing context rounding and avoiding enormous integer powers for tiny exponents. CSV uses strict parsing, validates fields, raw timestamp ordering, positive price/size, and receipt digest/count.
- A real behavioral regression existed in PR #8: `pg_try_advisory_lock` immediately rejected concurrent same-symbol imports. PR #12 uses `pg_advisory_lock` bounded by `lock_timeout=15000` and maps `LockNotAvailable` to `TimeoutError`. Restored the audited contract in PR #8 commit `77ee15376f868961bb7e629f56f2d58d56ba9cc1`.
- `statement_timeout=120000` remains; a timeout applies per SQL statement, not to the entire archive validation.
- Batch INSERT and checkpoint UPDATE execute inside the same transaction. Existing tests cover deduplication, conflict rollback, partial committed checkpoints, retries and unlock error preservation.
- PR #12 includes `write_drain.drain_thread_write`: a shielded task waits for actual synchronous thread completion before surfacing cancellation, preserving write/lock lifetime. This helper is **not present** in PR #8; integration must preserve PR #9/#12 cancellation-safe calls and shutdown gates. PR #8 synchronous importer does not itself invoke `asyncio.to_thread`.

## Evidence
- PR #12 candidate `13901274`: Storage integration run 39437433136 SUCCESS; CI run 39437432965 SUCCESS (Windows and Linux jobs).
- Previous PR #8 `206f02cd`: general CI SUCCESS; Storage integration FAILURE, consistent with lock contention behavior mismatch.
- Ten-case PostgreSQL coverage exists across PR #12's storage integration suite; individual case outcomes and exact test names were not independently retrieved. No claim of 10 fresh local PostgreSQL executions.
- Latest PR #8 SHA after lock restoration must receive its own exact-SHA Windows/Linux and PostgreSQL CI confirmation.

## Remaining risks / required gates
1. Re-run exact SHA CI and inspect failures, especially contention timeout test (can require ~15 seconds).
2. Exercise CSV/GZIP corruption, oversized/malformed numeric strings, extreme positive/negative zero exponent cases and bounded CPU/memory under fuzzing.
3. Verify `asyncio.to_thread` cancellation/drain integration from PR #9/#12, including shutdown while PostgreSQL is committing and avoiding premature DB close.
4. Test slow HTTP download, file-lock lifetime and cancellation in PR #6; these are outside this synchronous importer.
5. No merge, deployment, or production DB access. Historical completeness remains UNVERIFIED.
