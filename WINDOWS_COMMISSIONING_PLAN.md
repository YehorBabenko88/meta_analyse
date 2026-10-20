# Windows commissioning plan â€” 2026-10-20

Status: PREPARED, NOT EXECUTED on the independent PC. Prior candidate 9d1bfff5â€¦ and its logs are unavailable; user will supply later. Reported 586 passed / 10x67 are not independently certified here.

## Target and prerequisites

Separate Windows11 Pro PC; never LS5/LS-5/LS7/LS-7. Python3.12 x64, PostgreSQL18, installed MetaScalp. No exchange credentials. Obtain operator approval before executing this package. No automated deployment/installer for PostgreSQL, Python or MetaScalp is included.

Use a dedicated loopback database named meta_commission_<session>, owned by a dedicated app role, with no production data. Operator creates it using approved PostgreSQL administration. Runtime/preflight never create or delete the target database. Automated CI databases are ephemeral and separate.

## Package verification and setup (operator only)

1. Verify outer ZIP SHA-256 against the final audit report. Extract source.zip and metadata/evidence. CANDIDATE.json pins exact candidate SHA and every source file hash. Do not substitute a newer branch or install an unpinned mixture.
2. Confirm OS/CPU/RAM/disk and installed MetaScalp with commissioning/collect-host.ps1 -ExpectedComputer <TARGET> -MetaScalpExe <EXE> -Output host.json.
3. Run commissioning/prepare-environment.ps1 -ExpectedComputer <TARGET> -OperatorApproved. It only builds a local Python3.12 venv and installs pinned .[test,archive] after checking the target name. It has not been executed on the target by this auditor.
4. Set META_ANALYSE_COMMISSIONING_DSN in this shell to the dedicated local DB. Never log the password. Do not supply production DSNs or API keys.
5. Run .venv/Scripts/python.exe commissioning/preflight.py --manifest ../CANDIDATE.json --expected-sha <PINNED_SHA> --expected-computer <TARGET> --metascalp-exe <EXE> --output preflight.json --probe-public-rest. It checks source hashes, Windows11 Pro/Python3.12/PostgreSQL18, installed file and a verified public HTTPS GET. It does not migrate or write DB data, modify trust stores, or contact trading endpoints.
6. Operator approves read-only run explicitly: .venv/Scripts/python.exe commissioning/run_readonly.py --manifest ../CANDIDATE.json --expected-sha <PINNED_SHA> --expected-computer <TARGET> --log-dir <EVIDENCE> --operator-approved-readonly-run. The launcher denies POST/PUT/PATCH/DELETE before HTTP transport. Use only refresh/flow/history/paper controls; no live orders or level operations.

## Ordered hardware gates

- 30 minutes smoke: start/close at each startup stage; 1 then20 symbols; disconnect/reconnect; controlled network outage; archive cancel; pending SQL write. Require TLS validity, correct UNVERIFIED state, fresh-snapshot book recovery, responsive UI and no acknowledged shutdown before writes drain.
- 2 hours soak: same SHA, record samples every5s, reconnect/error counts, CPU/RAM/handles/thread count, persisted-event ages, Qt timer jitter; document bounded queue/backpressure and reconciliation explicitly.
- 24 hours stability: only after earlier gates pass; retain raw logs and UTC start/end, operator name, exact host/build/SHA/DB versions; reconcile data windows and duplicate IDs. No completeness VERIFIED claim from WebSocket alone.

Use commissioning/record-runtime.ps1 with AppProcessId from session.json, -Minutes30/120/1440, CandidateSha and target name. Observer success only means the observation duration elapsed; it is NOT an application-health PASS. Read-only launcher emits ui-runtime.jsonl and application.log. Queue depth/dropped-events are NULL until independently instrumented/reconciled, never invented as zero. Those unknowns must be resolved for final runtime acceptance.

## Evidence / stop / rollback

For every stage save host.json, preflight.json, session.json, application.log, UI/resource JSONL, observer-result.json, network/fault timeline, DB version/transaction snapshots and reconciliation report. A folder name or elapsed lab time is not evidence of a passed soak.

If writes remain active, window stays open and after10s reports incomplete shutdown; preserve evidence and let bounded DB statements finish/rollback. Do not kill/close the loop to manufacture success. Persistent OS/driver hangs remain NO-GO and require operator incident handling.

Rollback: close safely, verify worker gone and no app transaction active, preserve logs; discard only the dedicated test DB after explicit operator approval; reselect prior approved isolated source/venv. No main/production schema changes or MetaScalp level restoration are needed because this package does not perform them.

## Pinned release packet

Tested candidate: `13901274dac527f0aacfaf48481414b0971d6012`. Source ZIP SHA256: `5c7dc6bf58010b36cda876bb16367a538e9adeb38b41726ba153da7dd6246b76`. All 198 Git archive file hashes verified after extraction. Final reports and CI evidence are outside source.zip; frozen source reports may still say pending. Use the packet reports as the final verdict. Do not interpret package presence as approval: orderbook autonomous recovery remains NO-GO.
