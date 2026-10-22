# Independent PR18 acceptance corrections

Frozen audited PR18: `289c414011afdd52eb7b8dab6dbfd3166c8fdbcb` (tree `85af7270f78a91d987e6b4d9784339b4ae2e874d`). This change is a separate stacked Draft PR; PR18 and its base remain unchanged.

## Reproduced P2 findings

1. Both SCM endpoints need independent type/status validation. Equal-valued floats and booleans in `services_after` previously compared equal to integers in `services_before` and escaped strict validation. New tests cover all five contracts.
2. Explicit success markers are required. Missing or falsy non-string `error_stage` in SCM/config/module snapshots previously passed truthiness checks. Require the exact empty string in both endpoints.
3. Supplied topology cannot be ignored after a successful native image query. Validate complete supplied snapshots against native lifetime and CIM PID/parent/session/name; reject changes and malformed/missing endpoints. A successful file-backed path remains compatible when neither topology key is supplied. PID0/4 collector output is topology-only, so extra file/service proof is rejected rather than ignored. No arbitrary-PID kernel admission is added.

Independent synthetic regression on unchanged PR18: **175 failed / 10 passed**. Corrected combined seven-suite run: **718 passed**, two real-DPAPI tests deliberately deselected, no skipped/failed tests. Original service fixtures now include explicit successful SCM stages; production rules are tightened, not bypassed.

`python scripts/check_process_identity_mutations.py --output identity-mutations.json` runs fifteen source mutations entirely in memory. All fifteen must be killed by negative probes while all five full-proof service controls still verify. It mutates empty/duplicate SCM, image signature/hash, module membership, DLL signature, native PID lifetime, after-SCM validation, SCM/config/module stages, supplied topology, command arguments, arbitrary kernel admission, and special-PID mixed evidence. No source file is changed by the runner.

On frozen PR18, the same probe runner finds 30 negative admission gaps among 75 probes, kills nine applicable original guards, reports five new guards as inapplicable and one predicate as already failing its baseline. These are bounded probes, not mutation coverage of the entire application.

## CI and scope

Exact-head synthetic Windows/Linux jobs collect the seven explicit suites, require at least 718 passing unskipped JUnit cases and mandatory regression identities, then run the mutation gate. Public uploads contain only JUnit, source SHA/tree JSON and mutation result JSON after the privacy gate. Full/native/PostgreSQL jobs explicitly exclude this new branch for push and PR events. No target observation, native collector or live DPAPI is run. No collector/ABI/privilege change is made.

## Review base and limits

PR18 against frozen PR16 `e4a5c48e7155558a967868a7c8a696ab0e921dd3` has two commits and 13 changed files, versus 452 commits and 603 files against current main `2317c79d78654d8006d99b914532a089554677da`. A read-only exact-SHA comparison supports scoped review without changing PR18's base. Retargeting is a separate user decision: it changes the visible diff/review context and target dependency, not the candidate source SHA. Existing comments can become outdated; prerequisites remain to be reviewed before main integration. See [GitHub base-change documentation](https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/changing-the-base-branch-of-a-pull-request).

Remaining blockers: independent service implementation/mapped-byte attestation; PPL and QUERY_INFORMATION/VM_READ access; independent arbitrary-PID kernel identity; native ABI/layout and collector timing; physical ADMINIT authorization; PostgreSQL integration. They are not established by these synthetic checks. `assess_processes` still raises on some malformed outer-record shapes; the host boundary catches errors and blocks admission, so this is diagnostic robustness rather than a demonstrated admission bypass.

**ADMINIT remains NO-GO.** No native probe, live DPAPI, PostgreSQL, diagnose, Add-Type, target configuration changes, enrollment, smoke30, trading, merge or deployment.
