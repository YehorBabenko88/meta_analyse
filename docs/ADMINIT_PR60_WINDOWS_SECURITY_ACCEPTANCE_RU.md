# ADMINIT PR60 — независимый Windows Native/SCM/HTTP.sys Security Acceptance

Дата: 2026-10-26. Source-only GitHub review; physical ADMINIT NOT_RUN. **G0 FAIL_CLOSED, G1 NO-GO.**

## Exact candidate and source graph
PR60 HEAD `0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30`, tree `a85846d46df6e95f3d757e25399d991ee1db872b`, base `b6aeaf99ea00c3550a87f9ecde74a4e73bd248fe`. Five exact-head GitHub workflows reported SUCCESS. PR60 changes UI benchmark/CI files, not native/SCM/HTTP.sys runtime. The following blobs equal PR55:
`commissioning/host_identity.py` `40cdb27d8b98e49797e27bd3069aa9a597df34cf`,
`commissioning/process_identity.py` `69b1b5793aa2992017369a8309863c94c41f47cd`,
`commissioning/host-facts.ps1` `3fd04a385987d2fa9343e7a24e523f35d5867f21`.
PR60 native `process-evidence.ps1` blob `57ebcec365a929557a7f7d93c9f9b3c1a965a8be`, SCM adapter `native_scm_diagnostic.py` blob `223d283b7cc9c6ae1e882049790f776287d5f95d`, format-only PowerShell blob `ac2021608615773cf6e2b4aab8740165804f410f`, Python format-only blob `715e50c4fce6c27d6cf0ffdb6cce761027e7e427`.

## HTTP.sys and locale
Production `http_sys_owner()` only accepts a narrow English verbose queue profile; it must refuse unknown localized headers and multiple matching queues, contradictory process counts, malformed URLs, nonexclusive loopback, invalid PID. The operator's interactive `verbose=no` output cannot be compared as if it were `verbose=yes`. PR60 producer explicitly requests `view=requestq verbose=yes`, not an interactive default. Actual ADMINIT ru-RU labels/native bytes remain unknown; do not invent translations.
The format-only PowerShell child sets `[Console]::OutputEncoding=UTF8` before invoking system netsh; `$OutputEncoding` controls native stdin preference and cannot prove native stdout encoding. The child emits compressed UTF8 JSON; Python decodes utf-8-sig and applies strict duplicate-key rejecting JSON parsing. Valid outer JSON cannot restore mojibake from a mismatched native decoder. Format observer is diagnostic only: ownership NOT_EVALUATED, source checked before/after, lifetime NOT_EVALUATED, FAIL_CLOSED/NONE/exit1. It does not perform a PID ownership attestation.

## Windows Native and SCM
`OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)`, `QueryFullProcessImageNameW` flags0, `GetProcessTimes`, `QueryServiceStatusEx`, `QueryServiceConfig`, PSAPI VM_READ and kernel snapshot remain fail-closed. Win32 31 is generic failure; Win32 5 means access denied before module enumeration, neither proves PPL. Do not change token privileges or bypass PPL. PID reuse requires PID+creation FILETIME, kernel parent/session, paired native/module times and stable SCM membership. Registry and SCM service_type for KeyIso, SamSs, VaultSvc, DoSvc, wscsvc remain exact Python int==32 (not bool, float, mask or 16). ServiceDll source, loaded modules, signature and paired SHA256 remain mandatory. Co-occurrence is per member and diagnostic only; aggregate totals cannot identify one specific failing service or grant VERIFIED.

## Physical observations
Windows 11 Pro / PowerShell5.1 / ru-RU; MetaScalp1.0.291 ping responds; HTTP.sys includes 17845, TCP listener PID differs from MetaScalp PID, owner UNRESOLVED. Historical R0-R5 seven unresolved, QUERY_IMAGE Win31, module open Win5, Registry/SCM type refusals, SERVICE_RULE_UNREVIEWED, protection/architecture NOT_COLLECTED. No independent PR60 physical replay.

## PASS / FAIL / BLOCKED
| Gate | Status |
| --- | --- |
| Exact PR60 HEAD/tree and five hosted workflow conclusions | PASS metadata |
| Native/SCM predicates unchanged | PASS Git blob comparison |
| Producer verbose=yes / no forced ExecutionPolicy bypass | PASS source-only |
| HTTP.sys actual localized headers and native bytes | BLOCKED |
| PID lifetime and HTTP.sys ownership physical evidence | BLOCKED |
| Independent physical R0–R5 PR60 | NOT_RUN |
| Historical G0 | FAIL_CLOSED |
| G1 | NO-GO |

## P0/P1/P2
P0: no confirmed new VERIFIED path in reviewed unchanged native/SCM source. P1: localized verbose=yes output/encoding and queue ownership unresolved, and x64 native ABI/PPL runtime not independently accepted. P1: rare co-occurrence and format buckets can fingerprint a host across repeated reports. P2: historical Win31/Win5 root causes unknown; physical type correlation cannot be inferred from marginal totals.

## Operator-approved next diagnostic (not authorized by this document)
Only after explicit separate approval, one format-only observer run with exact clean PR60 SHA/tree and approved private output; no direct execution of raw `http-sys-format.ps1`, no transcript/raw netsh sharing. Operator confirms Windows PowerShell5.1, approved execution policy, no Bypass, trusted System32 netsh and no global encoding changes. Review only coarse booleans/buckets privately. If that format remains unsupported, stop: do not guess translations or promote owner. A full R0–R5 requires separate scope and admission after format review.

## Mandatory STOP
Source/tree mismatch or dirty checkout; changed collector hash; unknown/malformed localized output or Unicode; duplicate JSON keys; ambiguous queues/owners; nonexclusive loopback; PID/FILETIME or parent/session drift; Win31/Win5 on mandatory identity path; incomplete SCM/ServiceDll/module/signature/hash; unexpected VERIFIED; privacy leak; output failure; any requirement to modify PowerShell policy, code page, PPL, ACL, services, registry, Defender/Norton or PostgreSQL. Never retry with higher privilege to manufacture PASS.
