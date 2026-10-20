# Independent PR7 recovery audit

Candidate: 0086e338ee668f2fb1b4a9dd7253b16b8469ce13 (origin/audit-pr7).
Reviewed entire diff since 8ea8307: orderbook_stream.py, recovery tests and recovery document.
Source extracted using git archive into evidence/source; no checkout, shared repository edits or branch mutation.
Explicit PYTHONPATH evidence/source/src; probe log prints actual imported source origin.
Python: work/parallel-integration-audit-v2/.venv/Scripts/python.exe.
No real network, trades or database used. All socket connections monkeypatched.

## Results
- Focused candidate recovery/state tests: 26 passed.
- Broader orderbook/market collector/health/microstructure/telemetry suite: 44 passed in 0.67s.
- Independent invalid nonfinite delta injection: socket closes, new epoch receives fresh snapshot; old connection trailing delta never published.
- Independent sequence/update-ID regression injection: same fail-closed recovery; numeric upward jumps remain allowed by documented underlying Bybit policy.
- Established feed silence: watchdog reconnects and fresh snapshot recovers.
- Busy unrelated publicTrade traffic does not mask silence.
- Retained published snapshot stays independent and immutable across invalidation/recovery.
- Backoff observed exactly [0.1, 0.2, 0.4, 0.4, 0.4] with deterministic jitter.
- Stop event and task cancellation both interrupt an already-active 30s backoff immediately.
- Cancellation during receive closes socket promptly.

## Findings and acceptance
No new P0/P1 defect established in the reviewed recovery delta. Accept this candidate for the scoped autonomous recovery remediation, conditional on the parent audit's remaining candidate-wide checks; this is not approval for live commissioning.

Nonblocking inherited transport API caveat: cancelling run() directly after a valid snapshot closes the socket but leaves stream.books[symbol].valid True and sends no final gap (orderbook_stream.py:122-123). Old implementation also propagated cancellation without final invalidation. Integrated MarketCollector.stop cancels tasks and AnalysisSession._cleanup subsequently calls analysis.book_gap and health.gap; its final external on_gap invalidates the GUI. Retained BookSnapshot.valid is an observation-time value, so consumers must honor the on_gap channel rather than interpreting old snapshots as permanently live. This is not a newly introduced failure in the production shutdown path.

Artifacts: candidate-tests.log, market-regression-tests.log, independent_probes.py, independent-probes.log, backoff_shutdown_probes.py, backoff-shutdown.log.
