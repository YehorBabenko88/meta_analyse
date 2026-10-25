# Public CI evidence boundary

Based on immutable PR29 `0c255f4587b1293c8ede22a31636b7d24cfaced2`. Its four requested runs all completed success, but its checker accepts arbitrary identity/time/timestamp strings and inconsistent failure/error/skip counters. Independent synthetic witnesses establish source FAIL, not an assertion of actual credential exposure. PR24–29 are unchanged.

## Publication contract

All nine upload sites in the seven workflows in this tree now upload **only** `public-evidence/`, only after the projection/validation step succeeds, with missing files an error. The dedicated directory is built as a new sibling staging directory, fully validated then renamed into a previously nonexistent destination. Existing outputs are refused. Handled write/close/rename faults do not publish a partial directory. No raw fallback and no logs/native reports are included.

`project_public_ci_evidence.py` reads bounded raw JUnit using no user code. It rejects DTD/entity declarations/PI, malformed/oversize/deep XML, hidden nested results, contradictory counters and duplicate cases within a report. It preserves actual statuses and all four counters, strips raw metadata/properties/paths/details/stdout/stderr, and hashes each complete original identity into `public.tests/case_<sha256>`. Repeated identities in separate lifecycle reports are valid separate executions, not duplicate cases in one report.

`check_public_junit.py` accepts only this minimal public profile, verifies aggregate counters/statuses and rejects raw identity/time/timestamp strings, arbitrary properties, namespaces, comments/PI/DTD, symlinks and Windows reparse components. Its refusal message is fixed. The older regex scanner is retained only as defense in depth, explicitly not publication authorization. Existing legacy synthetic projector checks remain for their own tests/mutations; they are not used as an upload authority.

The manifest has exact inventory and SHA256 for all public files, raw input hashes without filenames, source SHA/tree/event/event SHA and run ID/attempt/job binding. `--validate` checks against current git HEAD/tree and actual Actions context, rejects missing/extra/changed files or replayed attempts. For PR events, the actual checkout is PR head and event SHA is the generated merge SHA, independently bound via event JSON. Failure projection can succeed as evidence while pytest/workflow stays failed: no continue-on-error or test-outcome override was introduced.

Typed mutation JSON retains existing schema/zero-survivor constraints. Linux PostgreSQL version receipts must be integers in major18, preserving server_version; mandatory tests still assert180001. Windows pinned binary provenance retains only the exact known public URL/hash/version/scope tuple. Other arbitrary JSON is not publishable.

## File inventory / integration

| Source files | Producer | Prior gate / risk | New public representation |
|---|---|---|---|
| diagnostic-tests.xml | Mandatory identity regressions | broad regex; raw runner metadata | hashed minimal JUnit |
| tests.xml and lifecycle10 tests.xml | Full OS suite / repeat_lifecycle_tests.py | raw hostname, parameters, status detail | one indexed JUnit per actual execution |
| tests.log, lifecycle tests.log | pytest/Tee logging | traceback/paths/env risk | excluded, private runner working files |
| pg18-tests.xml, pg18-lifecycle XML | PG18 workflow | unconditional raw upload | minimal JUnit, source, manifest |
| pg18-tests.log, postgresql.log | pytest/server | no strict schema | excluded |
| storage-tests.xml | Storage regressions | broad regex | minimal JUnit, source, manifest |
| archive-contract.xml | Archive HTTP/fault regressions | unconditional raw upload, no source receipt | minimal JUnit plus own exact source receipt and manifest |
| process-probe.json | Existing disposable Windows native step | broad regex over native diagnostic data | excluded; test step/check remains mandatory, no native evidence acceptance claimed |
| ui-performance.json | Existing benchmark | generic JSON | excluded; benchmark still runs |
| postgres-version.json / pinned Windows provenance.json | Existing version/pin checks | raw generic JSON/upload | typed version/pin JSON |
| kernel mutation JSONs | Existing 43 operator scripts | strict synthetic schema | same validated values, indexed safe JSON |
| synthetic test JUnit/source | Four synthetic workflows | old projection/checker mix | same bundle contract, no raw upload |

Historical registry workflows absent from this tree remain historical evidence, not enabled or rewritten. Existing published ZIPs are not deleted/replaced by this PR. Legacy branch-only uploads cannot be fixed retroactively without changing those source branches; this limitation must remain visible in the acceptance report.

## Threat model and limits

The runner extraction/work directory must be isolated and stable. Components reject symlink/junction/reparse/traversal and file identity changes at reads. This is accidental/race protection, not a proof against arbitrary privileged concurrent directory writers or an attacker rewriting the checked-out verifier/Actions environment. Atomic namespace publication does not prove power-loss durability; no fsync/physical crash claim. Raw hashes and case hashes are deterministic and not a general anonymization guarantee for low-entropy values. Metadata/SHA does not prove test semantics; independent raw-to-public/status/identity oracles are retained in tests and final review.

Local fault tests inject partial writes and rename failure; promotion mutants remove failure/error/skipped and are killed by the independent status oracle. Hosted Windows/Ubuntu Python3.12 tests and full integration receipts must be independently verified at the exact final HEAD, not transferred from prior runs. Skipped checks are BLOCKED. ADMINIT NO-GO, physical tests NOT_AUTHORIZED; no merge/deployment.
