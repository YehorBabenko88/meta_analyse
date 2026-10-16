# Order Flow incremental update follow-up

Spec: user request to audit PR #3 / commit897d3062 on codex/windows-lifecycle-audit-v2.
Execution: autonomous inline using systematic debugging, regression tests and verification-before-completion. No merge, force push, real orders or MetaScalp level writes. Excluded analytics files remain unchanged.

- [x] Reproduce Windows/Linux Actions failures. Original commit has invalid indentation and missing flow_diff module. Preserve concurrent author fix f92f1ec by rebasing only unpublished work.
- [x] Add Qt regression tests for changed rows, additions/removals/reordering, sorted visual positions, item identity and colors. Fix updates by symbol, retain existing items and sorting state; order numeric/text categories consistently.
- [x] Exercise 20 real WebSocket/DB connect-disconnect cycles and shutdown with all20 symbols/four subscriptions, including a pending native DB call and disconnect immediately before close. Diagnose debug-mode failures rather than relaxing deadlines.
- [x] Measure native Windows Qt under20k synthetic callbacks/s,20symbols,10Hz snapshots. Compare full replacement reference; report render percentiles, queue latency, Qt heartbeat, close latency, CPU and exclusions. Add portable benchmark to CI artifacts without machine-specific timing assertions.
- [x] Run full Windows/DB suite, independent review, Windows/Linux Actions. Commit focused fixes and test infrastructure, update PR body and attach exact-head evidence.
- [x] Produce docs/CODEX_ORDER_FLOW_FOLLOWUP.md and outputs report, keep original audit history and report remaining risks.

Review ledger: independent review confirms sorted-row mapping; found mixed numeric/text comparator cycle (regression reproduced) and insufficient full-startup gate in close test (now checks all40 subscribed topics). Debug stress exposed10-second WS close wait and transport leakage on repeat cancellation; testing bounded close and shutdown ordering.

Verification ledger: targeted lifecycle/table11 passed; fullsuite108 passed in77.03s with PostgreSQL+asyncio debug+warnings-as-errors and native exit0. Fixed transport close_timeout2 and owner-first shutdown; direct close/disconnect-then-close pass without leaked transports. Native Windows20k/s benchmark: partial p95render2.794ms, fullreference4.152ms. CI benchmarks added, timing values diagnostic rather than hardware-specific gates.

Final ledger: user authorized new branch/PR4 preservingPR3 history. Rebased onto6530b7e with base flow_diff/telemetry/tests unchanged; local fullsuite114 passed76.11s. Linux transient-state gate fixed by owner-loop barrier, both targeted variants pass. PR4 CI38770835567 includes latestbase9be7041: Windows117pass, Linux116pass+1expectedskip; both3s20k/s benchmarks pass and emitJSON. Native Windows10s benchmark recorded separately; independent review clean.
