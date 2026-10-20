# Windows commissioning plan â€” independent re-audit 2026-10-20

Pinned candidate: `446c72bd97cacc31f9937c9ab941d11539733be4`. This is a prepared package, not a deployment or a completed target test. Use the packet's reports, not older reports frozen inside source.zip.

## Stage admission

| Stage | Admission decision | Evidence needed before starting |
|---|---|---|
| Controlled 30-minute read-only smoke | CONDITIONAL GO only after all target prerequisites below pass; execution remains blocked until then | Exact trusted packet/SHA, approved separate PC, Windows11 Pro/Python3.12/PostgreSQL18/MetaScalp preflight, dedicated DB, operator present, logging |
| 2-hour soak | NO-GO | Reviewed successful30-minute target logs, clean shutdown, actual hardware/runtime behavior, queue/drop/reconciliation method and agreed resource limits |
| 24-hour stress | NO-GO | Reviewed successful2-hour target logs, resolved telemetry unknowns, recovery/reconciliation and resource trends within limits |

No stage is marked completed. Duration elapsed or automated CI success is not a real-PC acceptance result. If prerequisites cannot be demonstrated, retain NO-GO; no automatic promotion between stages.

## Separate target setup â€” operator only

Use a separate Windows11 Pro PC, never LS5/LS-5/LS7/LS-7. Install Python3.12 x64, PostgreSQL18 and MetaScalp through approved local setup; this packet does not deploy or install those products. Record OS/build, CPU/RAM/disks, Python, PostgreSQL, MetaScalp version and executable hash. No exchange credentials or production DSNs.

1. Verify outer ZIP SHA256 against the independently supplied checksum. Extract the packet, then extract source.zip in the same directory: `source/` and `CANDIDATE.json` must be siblings. Work from `source/`. Do not mix editable installs or source branches.
2. PostgreSQL operator creates a new dedicated local role and loopback database named `meta_commission_<session>`, with no production data. Use an interactive password prompt; never paste passwords into commands/logs/reports. Do not grant access to production DBs. The app writes its test schema only in this dedicated database.
3. `./commissioning/collect-host.ps1 -ExpectedComputer <TARGET> -MetaScalpExe <EXE> -Output <LOGDIR>/host.json`
4. `./commissioning/prepare-environment.ps1 -ExpectedComputer <TARGET> -OperatorApproved` creates a local Python3.12 venv and installs pinned `.[test,archive]`; no global installation or production migration.
5. Set `META_ANALYSE_COMMISSIONING_DSN` to the dedicated loopback DB in this shell. Required dbname prefix: `meta_commission_`. Service overrides and remote explicit/inherited hostaddr are rejected. Remove BYBIT_API_KEY/BYBIT_API_SECRET. Keep credentials out of saved logs.
6. `./.venv/Scripts/python.exe commissioning/preflight.py --manifest ../CANDIDATE.json --expected-sha 446c72bd97cacc31f9937c9ab941d11539733be4 --expected-computer <TARGET> --metascalp-exe <EXE> --output <LOGDIR>/preflight.json --probe-public-rest`
7. Preflight must pass exact source hashes/imported package identity, Windows11 Pro/Python3.12/PostgreSQL18, installed executable and verified public application HTTPS GET. Do not bypass TLS errors. Optionally collect direct IPv4/IPv6/default-trust diagnostic separately with `scripts/verify_rest_tls_windows.py`; a missing IPv6 path alone does not disprove the actual working HTTPS path. Diagnostic DNS resolution can depend on OS resolver behavior.
8. Only after explicit operator approval: `./.venv/Scripts/python.exe commissioning/run_readonly.py --manifest ../CANDIDATE.json --expected-sha 446c72bd97cacc31f9937c9ab941d11539733be4 --expected-computer <TARGET> --log-dir <LOGDIR> --operator-approved-readonly-run`.

Launcher permits only GET/HEAD/OPTIONS through application ManagedAsyncClient, pins the local test DSN, and refuses trading credentials. It is not a general OS sandbox. Never exercise level creation/deletion or trading controls. Paper mode is retained but no live orders are allowed.

## Controlled smoke sequence and evidence

Run one instrument first, then up to20. Exercise start/stop, watchlist changes and sorting; close during REST startup, schema initialization and active load; repeat connect/disconnect; perform an operator-controlled network outage and restore. Expected feed states remain UNVERIFIED/STALE until appropriate fresh observations; PROVISIONAL does not certify complete history. Invalid/regressing frames must cause a new epoch and require a snapshot before deltas publish. Bybit numeric update/seq jumps alone are not a documented contiguous counter and must not be treated as proof of a lost message.

Record UTC fault timeline, expected/observed state transitions, reconnect epochs, successful fresh snapshots, archive import/checkpoint outcomes and shutdown observations. Validate book/tape/OI/Diagnostics separately. Do not infer exchange completeness from one fresh book.

`./commissioning/record-runtime.ps1 -ExpectedComputer <TARGET> -AppProcessId <PID-from-session.json> -Minutes 30 -OutputDirectory <LOGDIR> -CandidateSha 446c72bd97cacc31f9937c9ab941d11539733be4` records resources every5s. Save session.json, application.log, ui-runtime.jsonl, resources.jsonl, observer-result.json, host.json, preflight.json and DB/reconciliation observations. Observer completion only proves observation duration; health stays NOT_EVALUATED until review. Queue depth/dropped counts remain NULL/UNVERIFIED; this blocks longer-stage promotion until measured/reconciled, not silently converted to zero.

## Immediate stop conditions

Stop the test workload and request normal disconnect/close on any of:

- Wrong host/source/hash, non-dedicated or remote database, unexpected credentials, attempted HTTP write/trading/MetaScalp mutation.
- Certificate/hostname verification failure or proposed insecure fallback.
- Invalid/stale/gapped data presented as verified, stale book reused across epochs, no fresh-snapshot recovery after restored connectivity, or sustained reconnect storm.
- Lost/duplicate/conflicting rows, non-atomic checkpoint, original DB error hidden by cleanup, unexplained persistence or reconciliation mismatch.
- Stop/close acknowledged while writes remain active, leaked worker/socket/task, unresponsive GUI, uncontrolled resource growth or missing evidence.

A scheduled network fault is not by itself a failure: evaluate fail-closed state and recovery. Document the observed bound; default stream silence watchdog is90s with bounded jittered reconnect up to60s, while UI freshness policy is separate. Do not invent an immediate recovery guarantee under blocked callbacks/network failures.

If close reports incomplete shutdown after10s, do not force-kill to manufacture a PASS. Preserve logs and let bounded SQL complete/rollback. Persistent driver/OS hangs, failure to regain safe state or uncertain writes leave NO-GO and require operator incident handling. No unattended soak.

Rollback: safely stop, verify worker exited and no app transaction remains, preserve evidence, retain only the dedicated test DB until operator-approved disposal, and select a previously approved source/venv. Never alter main/production/MetaScalp levels as rollback.

Source ZIP SHA256: `91d0c081ce0d58067c7a64f6faa96be558ef6e06d60739aa3d44220b6559169c`; all316 Git archive file hashes verified after extraction. No target runtime has been executed by this auditor.
