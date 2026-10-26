# META_ANALYSE_HOSTED_FINAL_ACCEPTANCE_RU

2026-10-26. Независимый GitHub Actions Security/Privacy/Provenance аудит PR #52–#55. Ни merge, deployment, physical ADMINIT, rerun или отмен.

## Exact HEAD и runs

| PR | Exact HEAD | Hosted состояние |
|---|---|---|
| #52 | `8a1c20184cbd878097f62530fc07630568fb7f84` | Push `40295973256`, PR `40295979565`: все три обязательных jobs в каждом SUCCESS, attempt 1 |
| #53 | `bbbc1cc75f9bb15490867227396267ba81eaf9b0` | CI PR `40301079889`: archive SUCCESS, Windows FAIL, Linux FAIL, attempt 1 |
| #54 | `0883a979ba364a778a3ca78d0dc4fdc5026e46d7` | Final synthetic push `40304095378`: 3 jobs SUCCESS; PR `40304103792`: 2 synthetic SUCCESS, PG job in_progress at inspection; Kernel `40304103756`: Ubuntu FAIL, Windows CANCELLED |
| #55 | `edc8e831c202e3597e27532359ab9c47a9f29a88` | Push `40305948528`: 2 synthetic jobs in_progress; PR `40305960447`: Windows in_progress, Ubuntu queued at inspection |

Tree SHA for each new candidate must be bound to exact authenticated run `head_commit.tree_id` and Git commit API before final PASS; no previous-head transfer.

## Verified PR #52 public evidence

Six original ZIP artifacts downloaded by ID. Their SHA256 from GitHub API:
- Push Ubuntu `12638510930` `4b78e324b1e67c6cd88af1145f14232a38f80feb0898fc8f82c3bf3b4fd1d748`
- Push Windows `12638491012` `61dab7b5f366f426cd9ba3210d37eb9ad0c9922eacb3d8c7d8b81f6136d02194`
- Push PG18 `12638077494` `9051ca56ee57ce403ac0dcb2d2f15953aa508118e7f0c726f2edfaf6101a0e12`
- PR Ubuntu `12638475826` `2bf18553a187cc4367bbfae0ad341ebde9d44cb6e4ad4a87264b139f2fbb7db4`
- PR Windows `12638580979` `af23dad5e4a31edfa32c7ddc97e5adaf7e1674368cee7ceeacec70af16d32c5c`
- PR PG18 `12638665848` `65456ec3673cf6ccdb69d4e9f2587af93fdb7cce5756b084a782cd2a2af10236`

Independent previous review verified local ZIP hashes against API, inventory, manifest file hashes and source SHA/tree/run/attempt/job; 1744 projected PASS each Windows/Linux and 4 PG18.1 PASS each run, zero failures/errors/skips. PR #52 **bounded hosted PASS**, not physical G1. Raw-JUnit identity oracle and failure-path independent witness remain open.

## Confirmed hosted failures

### PR #53 — run 40301079889 (FAIL)

Windows job `121498837331`: **4 failed, 2390 passed, 4 skipped, 1 error**; failures include `git show 4a92643...:commissioning/process_identity.py` missing in frozen object, subprocess/native-boundary expectation failures and unraisable `Popen.__del__` warning. Privacy projection also failed closed; no Windows public ZIP published.

Linux job `121498837452`: **4 failed, 2389 passed, 5 skipped**; concrete failures:
- `test_final_active_boundary_denies_live_database`: psycopg connection string parsed before intended synthetic refusal.
- `test_final_active_boundary_denies_native_child`: `powershell.exe` unavailable on Linux before intended guard.
- `test_final_http_boundary_rejects_external_request_before_dns`: expected refusal pattern mismatch.
- `test_shared_predicate_refactor_is_equivalent_to_frozen_pr39`: immutable git object does not contain requested `commissioning/process_identity.py`.

Linux public ZIP `12642206902` and archive ZIP `12641443381` were uploaded. Their existence does not change workflow FAIL; must inspect privacy and hashes separately. **P0 FAIL** for #53 CI.

### PR #54 — Kernel run 40304103756 (FAIL)

Ubuntu job `121508826628`: 948 tests passed / 2 deliberately deselected; mutation gate reports `survived=0`, `inapplicable=1`, then exits 1. This is **real mutation-gate FAIL**, not a test PASS. Privacy projector also refuses mutation receipt, and no ZIP is published. Windows job `121508827096` CANCELLED; not PASS. Need root-cause investigation before any rerun; mutation inapplicable must not be reclassified as PASS.

## Current artifact inventory for #54/#55 (partial)

#54 push `40304095378`: 3 ZIP IDs `12643531096`, `12642871706`, `12642828282`; all three jobs SUCCESS. #54 PR `40304103792`: synthetic ZIP IDs `12643456155`, `12643286858`, PG ZIP ID `12642609349` published while PG job still in_progress. Do not mark run PASS before terminal status.

#55 push `40305948528`: Windows ZIP `12643197822`, Ubuntu ZIP `12642204531` already present but jobs were in_progress; PR `40305960447` artifacts 0 at inspection. Stale/in-progress artifacts cannot imply full acceptance.

## P0/P1/P2

- **P0 FAIL:** #53 real hosted CI failures; #54 Kernel mutation gate fails on `inapplicable=1`.
- **P0 BLOCKED:** #54 PR PG job terminal confirmation and #55 push/PR exact hosted completion; cannot infer PASS from ZIP presence.
- **P1 BLOCKED:** full new ZIP SHA256/inventory/manifest and JUnit raw-to-projected identity oracle for #54/#55; privacy failure-path on #53/#54 must be independently assessed.
- **P1 PASS (fail closed):** #53 Windows and #54 Kernel privacy gate did not publish rejected raw JUnit/mutation artifacts.
- **P2 OPEN:** raw GitHub logs privacy, historical/stale attempts, immutable oracle fetch path, explicit allowed skips/deselections and negative XML/JSON parser suite on new HEAD.
- **ADMINIT physical G0/G1: NO-GO.** Hosted disposable PostgreSQL 18.1 cannot authorize physical G1.

## Recommendations

1. For #53, repair synthetic test boundary/oracle availability on a **separate** Draft PR with red/green tests; do not weaken production guard or turn missing frozen git object into PASS.
2. For #54, identify why one mutation became inapplicable, preserve `inapplicable > 0` as FAIL, and add a deterministic regression.
3. Wait for terminal #54/#55 jobs. Independently download all ZIPs by artifact ID and validate SHA256, manifest, source/tree/run/attempt/job, XML/JUnit identities and privacy; verify raw logs separately.
4. Do not count policy-SKIPPED legacy workflows as PASS. Do not rerun without diagnosed cause, mass cancel or merge.

**Verdict: #52 bounded hosted PASS; #53 FAIL; #54 mixed SUCCESS/FAIL/BLOCKED; #55 BLOCKED. Overall integration acceptance BLOCKED.**


## Update: PR #54/#55 hosted runs and real artifacts (2026-10-26)

Exact HEADs unchanged: #54 `0883a979ba364a778a3ca78d0dc4fdc5026e46d7`; #55 `edc8e831c202e3597e27532359ab9c47a9f29a88`.

PR #54 final synthetic PR run `40304103792` is now **terminal SUCCESS**, attempt 1, three jobs SUCCESS (Windows, Ubuntu, disposable PG18). Three ZIPs downloaded and independently SHA256-matched against GitHub API:
- Ubuntu artifact `12643456155`: `ad715e8494195d810422ebfc5614ff822f60a9f55e6b1c87942f5801379b84b3`
- Windows artifact `12643286858`: `db5399757391b146235dcb542ee702c866c40d28cc542fb7dab1750fa87573e9`
- PG18 artifact `12642609349`: `d0889e84b338f71b8d7b0efeae0064fe9b38e4e01610902318ac21d3da1a2fde`

PR #55 push run `40305948528` and PR run `40305960447` are still **not terminal**: each has Windows and Ubuntu synthetic jobs SUCCESS, disposable PG18 job in_progress / queued respectively, attempt 1. Four synthetic ZIPs downloaded and independently SHA256-matched:
- Push Windows `12643197822`: `ccd3cc4af8cc3e723fa3ac62033151473293ec3e11cbbab9094d936567ef21b6`
- Push Ubuntu `12642204531`: `aa5c7e98e0a9067c2226ae4600651638ac4376f44865e4678434dc6de21570f2`
- PR Ubuntu `12642363516`: `791adb46e7a4bf2c38be77c1d34f656e5de1e37df8a6c806e95ea7615821191f`
- PR Windows `12642259869`: `d2560eeeb852e454add3e4d2cbbbfe8715289e2f85d8ae4746d8d0c0d19df87d`

The downloaded ZIPs' manifest/file hashes and exact source/run/attempt/job bindings were checked, and projected JUnit status counts/privacy were reviewed. These results are **bounded evidence for those seven artifacts**, not whole-run acceptance while dependent PG jobs are unfinished. The #54 independent Kernel workflow `40304103756` still FAIL (mutation inapplicable=1, Windows cancelled); no success reclassification. The #53 full CI remains FAIL. Policy-SKIPPED legacy workflows are not PASS. ADMINIT physical G1 remains NO-GO.
