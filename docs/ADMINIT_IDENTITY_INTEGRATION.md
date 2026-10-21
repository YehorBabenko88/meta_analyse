# PR 15/16/17 identity integration

## Scope and provenance

Integration branch: `parallel/adminit-identity-integration-20261021`.
Base is exact PR #16 HEAD `e4a5c48e7155558a967868a7c8a696ab0e921dd3`, which includes PR #15 `69969c983335d784cff8930c7e95ec06d56de214`.
Only the single own commit of PR #17, `d88ef890327dbe8a8e4cce211e28e53f584d39ab`, is cherry-picked; its merge-base with #16 is `3f4185fdb61ec1bab590203161cfc8face55335a`.
No source branch is rewritten. The integration is proposed as a separate Draft PR targeting the default branch; it is not authorization to merge.

## Integration adjustments

- Adapt the standalone #16 fixture with explicit zero `win32_error` required by #17. The initial combined run had 303 passes and 9 failures, all caused by that incomplete fixture; the classifier was not relaxed.
- Exercise all 28 existing service proof faults against each of five contracts, plus all nine missing evidence sources for every contract.
- Reject float/bool substitutions for SCM PID/state, module PID/creation/error, and service configuration type. New negative tests initially produced 30 failures/5 passes because Python numeric equality admitted malformed identities. Exact integer checks close those paths; no admission rule or contract is added.
- Independent review found missing/nonzero SCM error status could verify. Require explicit integer-zero SCM status and coherent successful native image-query status. All 27 new cases failed before correction; the final candidate passes them. Adapt old synthetic service fixtures with explicit success status.
- Reject raw kernel snapshot keys in public artifacts. Two new privacy tests failed before the scanner correction.
- Extend exact-head Windows/Linux synthetic CI to all six identity/service suites. Both real DPAPI cases are deselected. No native collector or PostgreSQL is invoked. Native/full/database jobs explicitly skip this integration branch on push and PR events; these skips are not positive runtime evidence.
- Require at least 533 unskipped, passing JUnit cases and mandatory regression test names. Upload only `source-sha.json` and `kernel-tests.xml` after the privacy gate succeeds. Exact checkout SHA and tree are recorded independently of the PR merge SHA.

## Acceptance checks

Signed lsass/svchost with empty SCM and duplicate SCM remain UNRESOLVED. Valid ordinary System32 images retain the existing signature/path/hash/SCM checks. All five contracts require unchanged complete SCM/configuration, exact native lifetime/host, reviewed command/account/type, loaded modules, and signed/hash-stable/reparse-safe DLL evidence. Arbitrary kernel-like PIDs do not acquire an admission exception. Missing/changed native and topology evidence, PID reuse and tested malformed types fail closed.

Local isolated Windows validation before candidate commit: 533 passed, 2 deliberately deselected real DPAPI tests, 0 skipped/failed; JUnit gate and explicit artifact privacy gate pass. Constrained venv dependency check, compileall and diff checks pass. Final exact-SHA hosted results belong in the PR and external verification report, not this self-referential commit.

## Limits

ADMINIT remains **NO-GO**. Synthetic evidence establishes classifier behavior only. Independent kernel identity is still unavailable for the historical arbitrary-PID cases. Disk signatures and loaded-module paths do not attest mapped bytes or service dispatch. Native ABI/layout, protected-process access, collector timing/performance and physical-host admission are not validated. Privacy scanning is bounded defense in depth, not proof against arbitrary secrets.

No live DPAPI, native probe, ADMINIT diagnose, Add-Type execution, PostgreSQL, Norton/ACL/service/registry/Grid changes, enrollment, smoke30, trading, merge or deployment is performed by this verification.
