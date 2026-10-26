# PR60 G0 preflight implementation plan

**Goal:** prepare independently reviewable PR60 operator evidence without executing a physical probe.
**Architecture:** an offline strict record evaluator and exclusive new receipt writer in scripts/, three operator runbooks. No collector/runtime/predicate modifications. Evidence is operator supplied, not self-authenticating; externally approved baseline digest is a required trust input. Always FAIL_CLOSED/NONE/exit1, even when records are consistent.
**Spec:** user's PR60 Final G0 Readiness requirements; exact target 0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30 / a85846d46df6e95f3d757e25399d991ee1db872b.

## Constraints and rulings

- User authorizes necessary code, tests, isolated Draft PR and hosted verification autonomously; no additional design approval needed. No physical G0/G1–G5, live collector/DPAPI/PG, merge/deployment/system changes.
- Preserve PR60 and src/commissioning bytes. Control code is separate from the immutable PR60 target. No invented baseline/tool approval.
- No automatic probe from the evaluator. Format-only and native are mutually separate operator decisions, never an automatic chain.
- Namespace writer bounds accidental aliasing/races using exclusive create and strict ancestor checks; hostile same-user/admin concurrent mutation and crash durability are not proved. Unknown/excluded isolation is BLOCKED.

## Review focus

- Self-measured hashes must not approve their own baseline: missing/wrong externally supplied digest blocks.
- Missing/malformed bool, enum, signature/basis, source/lifetime and policy fields block without raw disclosure.
- Existing hardlinks/symlinks/junctions and output collisions never truncate prior evidence.
- AllSigned with unsigned scripts, any Bypass/Process override, unreviewed Add-Type/temp chain block.
- Source/CI readiness never authorizes physical execution; actual host provenance remains NOT_ATTESTED until independently supplied and reviewed.

## Tasks

- [x] Freshly verify PR60 ancestry, 11 Actions, 29 ZIP, JUnit/provenance/privacy and concrete uploader jobs.
- [x] RED tests for offline record validation and exclusive output; implement scripts/g0_preflight_contract.py only after RED.
- [x] Write ADMINIT_PR60_G0_PREFLIGHT_RU.md, ADMINIT_PR60_HTTP_SYS_FORMAT_RUNBOOK_RU.md and ADMINIT_PR60_R0_R5_ONE_SHOT_RU.md with literal PR60 source pair.
- [x] Enable current branch in existing mandatory workflows; include new module in selected identity gate, preserve every previous job/test.
- [ ] Local selected/full offline, strict privacy/JUnit and independent whole-branch review; commit/push separate Draft PR.
- [ ] Verify new exact-HEAD hosted jobs/real artifacts; publish bounded readiness matrix and remaining physical blockers.

## Review ledger

Independent reviewer found P2 numeric 0/0.0 source signature flags comparing equal to False. Eight RED cases reproduced readiness promotion; exact-bool fix yields 95 GREEN module cases. Additional RED case for malformed unused baseline group also fixed. Re-review: no remaining actionable findings. No authorization bypass was claimed; all reports remained FAIL_CLOSED/NONE.

Ruling: CLR and native DLL provenance are COMMON to format-only and R0 because format uses token/system-directory ctypes and PowerShell CLR. Two source-derived RED controls reproduced missing coverage; both now BLOCKED. Only C# compiler remains R0-only. Final module97 GREEN; independent re-review clean. Superseded own control9af1b5d CI is cancelled rather than treated as current evidence. PR60 and other branches untouched.
