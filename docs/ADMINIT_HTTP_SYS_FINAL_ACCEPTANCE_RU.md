# ADMINIT_HTTP_SYS_FINAL_ACCEPTANCE_RU — независимый source audit, 2026-10-26

## Decision
**HTTP.sys ownership remains UNRESOLVED; physical format-only probe requires separate operator approval; G0 FAIL_CLOSED, G1 NO-GO.** No physical ADMINIT or netsh execution by reviewer.

## Exact identity and ancestry
PR54 HEAD `0883a979ba364a778a3ca78d0dc4fdc5026e46d7`, tree `b10b07c888e8fd3e95c97ed5945479cde7196b5a`, parent/base PR52 `8a1c20184cbd878097f62530fc07630568fb7f84`.
PR55 HEAD `edc8e831c202e3597e27532359ab9c47a9f29a88`, tree `84e128ca44e2ffe54bda7c003d0358a0b8d8b8fd`, parent/base PR54 exact HEAD. PR55 changed only workflow/tests/encoding report/checker, not production host_identity.py/http_sys_format.py/http-sys-format.ps1.

## Code review
- `http_sys_owner()` supports a narrow English verbose queue grammar; exactly one matching exclusive loopback queue, one active process and valid positive PID are required. Malformed/duplicate count, trailing URL text, ambiguous queues, nonloopback HTTPS and missing English labels refuse. The actual localized netsh headers on ADMINIT remain unknown: do not guess translations or relax acceptance.
- `http-sys-format.ps1` sets child Console.OutputEncoding to UTF8, executes system `netsh.exe http show servicestate view=requestq verbose=yes`, and emits one compressed JSON object. The raw netsh output is internal to the child; do not execute the script directly or redirect raw streams publicly.
- `http_sys_format.py` launches system WindowsPowerShell5.1 with `-NoProfile -NonInteractive -File`, no `-ExecutionPolicy Bypass`, captures bounded stdout, parses strict UTF8-sig JSON, and uses `evidence_schema.strict_loads` to reject duplicate keys. Unexpected schema, nonzero child exit, malformed Unicode and excessive text must fail closed. UTF8-sig allows a leading UTF8 BOM; this is a deliberate transport allowance, not acceptance of arbitrary BOM placement.
- OutputEncoding is native stdin preference; no stdin pipeline is used. Console.OutputEncoding controls PowerShell's native stdout decoder, but synthetic cp866/UTF8 tests do not reveal actual netsh emitter encoding. Outer console cp866 does not prove child decoder state. A valid JSON wrapper cannot repair previously misdecoded Cyrillic.
- Format-only projection returns fixed buckets, booleans and enums, `ownership=NOT_EVALUATED`, `format_support=NOT_ATTESTED`, lifetime NOT_EVALUATED, status FAIL_CLOSED, authorization NONE and exit1. No VERIFIED path is added. Source SHA/tree and collector identity are checked before/after capture; this does not prove target PID lifetime.

## Privacy
Only coarse structural bucket/boolean report may be considered for chat after manual review. Even target-token presence, Cyrillic/non-ASCII flags, line counts and repeated runs may fingerprint a rare host. Do not send raw netsh text, URLs, queue names, PID, SID, paths, hashes, usernames, labels, raw localized headers or exact per-queue counts. Prefer `status=FAIL_CLOSED`, `ownership=NOT_EVALUATED`, `format_support=NOT_ATTESTED` and broad `locale_profile=UNKNOWN`. Do not assert anonymization.

## Matrix
| Check | Status |
| --- | --- |
| Exact PR54/55 SHA/tree and ancestry | PASS |
| Narrow English parser and fail-closed source review | PASS source-only |
| Strict JSON duplicate-key transport | PASS source-only |
| Synthetic PS5.1 cp866/UTF8 × stdin encoding | AUTHOR-REPORTED 8/8, independent replay NOT_RUN |
| Hosted PR55 run 40305960447 | QUEUED / BLOCKED |
| Real ADMINIT netsh encoding/localized labels | UNKNOWN / BLOCKED |
| Physical format-only observation | NOT_RUN |
| HTTP.sys owner VERIFIED | NO, UNRESOLVED |
| G0/G1 | FAIL_CLOSED / NO-GO |

## P0/P1/P2
P0: no confirmed new VERIFIED bypass in reviewed delta. P1: actual netsh format and byte encoding unknown; source-only parser acceptance cannot be upgraded to physical owner verification. P1: rare structural output needs privacy review before chat/public publication. P2: UTF8-sig leading BOM is permitted by transport contract; synthetic test coverage cannot establish native netsh behavior.

## Minimal operator-approved format-only runbook
1. Separately approve exactly one format-only diagnostic, exact PR55 SHA/tree, Windows PowerShell5.1 host and private output location. Review script source and operator token; no global encoding or ExecutionPolicy changes.
2. Confirm clean checkout, trusted source binding and absence of raw stdout/stderr redirection, transcription, shell history payloads and public uploads. Do not execute raw `http-sys-format.ps1` directly.
3. Only if approved, run the reviewed `commissioning/http_sys_format.py` entrypoint with exact `--expected-sha`, `--expected-tree`, and a new private `--output` path. No additional native collector, HTTP requests or process probing. The command always returns exit1 as a deliberate FAIL_CLOSED diagnostic; do not treat it as success or rerun automatically.
4. Review private output locally. Publish only a manually privacy-reviewed fixed-field summary, never raw netsh lines or rare detailed combinations. Do not use this format probe as owner admission.

## Mandatory STOP
Wrong HEAD/tree, dirty worktree, changed collector identity, non-approved token/host, ExecutionPolicy block, unexpected raw output, UTF8 decode/JSON duplicate/malformed Unicode, nonzero netsh child, oversized output, multiple/ambiguous queues, spoofed labels/URLs, unknown format, source drift, private output failure, or any attempt to promote UNRESOLVED to VERIFIED. On any STOP, preserve fail-closed and do not change Norton/Defender, Windows locale, code page, HTTP.sys, ACL, registry or services. No G1.

## Follow-up CI review (2026-10-26)
PR54 kernel identity workflow run 40304103756: Ubuntu synthetic job FAILURE after 948 passed / 2 deselected, due to `project_public_ci_evidence.py` returning `BLOCKED: public CI evidence rejected`; Windows job CANCELLED. This is a publication/provenance gate failure, **not** a parser or kernel unit-test PASS for the whole workflow. No relaxation of publisher is authorized. PR55 synthetic run 40305960447 was IN_PROGRESS at review; PR57 CI 40307440535 QUEUED. Do not transfer earlier-head results.

## Additional exact PR55 hosted job inspection
Run 40305960447: synthetic ubuntu-latest and windows-latest jobs are both completed SUCCESS; dependent disposable-postgres18 is QUEUED. Two artifacts are listed by GitHub API, but ZIP bytes, SHA256, JUnit identities and provenance have not been independently inspected in this audit. Whole run is not yet an accepted PASS. PR57 CI run 40307702974 was QUEUED at inspection. Physical HTTP.sys ownership remains UNRESOLVED.
