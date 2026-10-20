# Blockers and remediation — 2026-10-20

Overall **NO-GO**. Verdicts refer to candidate 13901274dac527f0aacfaf48481414b0971d6012, not unavailable 9d1bfff5….

| Blocker | Evidence and remediation | Independent verdict | Remaining acceptance condition |
|---|---|---|---|
| REST TLS failure | Verified app GET200, TLS1.3, cert/hostname verification on current audit host; no bypass. Old failure not reproduced or explained | CONDITIONAL GO for controlled test on current host | Real target successful preflight; capture original exception/CA/proxy chain on failure |
| Archive validation stalls | Tiny-exponent and positive-exponent zero hangs reproduced; bounded conversion and zero-first fix. Concurrent imports restored with bounded native SQL wait. Ten mandatory real PostgreSQL regressions | GO for scoped automated validation/import fixes | Hardware archive cancellation/load and unknown malformed inputs remain runtime checks |
| Orderbook recovery | Strict malformed-state rejection and fresh-snapshot reconnect pass. Fault probe shows invalid delta does not initiate reconnect/resubscribe; delta-only healthy session remains invalid | NO-GO for autonomous recovery | Define bounded recovery/resubscription after invalid frames and silent feed, then fault-test and target network outage |
| Unfinished writes after shutdown | Collector writes and monitor schema initialization now retain ownership until completion; repeated-cancel/rollback/error regressions pass | CONDITIONAL GO for controlled commissioning | Target close during real archive/SQL activity, no active app writes after acknowledged stop; stuck-driver incident policy |
| Separate Windows11 Pro commissioning | Package prepared and hash-verified; actual hardware/MetaScalp logs absent | NO-GO | Approved 30m, then 2h, then 24h logs on exact SHA with reconciliation |

Additional audit fixes: corrected actual-NUL advisory regression key; increased mandatory PG gate to ten; protected manifest/import identity and hidden libpq routing. No warnings suppressed, fixed sleeps substituted for synchronization, timeout enlarged, TLS weakened or gates relaxed.

For write-drain precision: early stop acknowledgment was proven; writes after actual worker/process exit were not. Existing Qt thread waits executor shutdown and reports incomplete close after 10s without pretending it succeeded.
