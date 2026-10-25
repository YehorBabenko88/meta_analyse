# WINDOWS_ADMINIT_PR47_ACCEPTANCE_RU — независимый Windows Native/SCM audit

Дата: 2026-10-25. **Решение: G0 FAIL_CLOSED; G1 NO-GO.** Ни физический ADMINIT, ни native collector, ни PostgreSQL, ни Windows services не запускались этим аудитором.

## Exact Git identity
PR47 HEAD `59626930a911c0dde330f7760c78ccd99468a1f4`, tree `5cff9cedffa5b65f3bfb351e851370ff28d7aca7`, base/merge-base PR43 `a04f132d64db0981ef93de1be8208612de08a194` (tree `d9b0c63525bb8bc28464002e676caee5a5ce626e`). Исторические PR HEAD/tree: #31 da0fb4735d2019e0ffa8b9f796b73725272daa5f / 3aa3e5701780d07e36404cd9886b8454cce08aed; #33 47a727c34f6894e2f844741487bb0ac5d571cb75 / 9b0673160885b8628d1e11b3981248dcd6a23bab; #39 4a92643c00a7e4d113025e1df427d8f4850f0981 / 56d46ecedea438769b673ecbf720fd06e32567ed; #40 16f5299e1b83bb4e527563e39fd889a4f90aaffa / d80c43f9e6dd54a6e0576d1181603dded4e8a3eb; #41 5b622cc218fdf90d26164d544176dd647297fc53 / 210d69f19d3912013414e550da04594e6b7fd3f2; #42 cef0155fc1fa1a5d031908bde7f54369f34a8b55 / 574a587739f43d9736b4ba279e16daf2be51a9f6; #43 a04f132d64db0981ef93de1be8208612de08a194 / d9b0c63525bb8bc28464002e676caee5a5ce626e.

## Independently verified Git blob identity (PR43 == PR47)
- commissioning/process-evidence.ps1: `57ebcec365a929557a7f7d93c9f9b3c1a965a8be`
- commissioning/process_identity.py: `69b1b5793aa2992017369a8309863c94c41f47cd`
- commissioning/native_scm_diagnostic.py: `223d283b7cc9c6ae1e882049790f776287d5f95d`
- commissioning/host-facts.ps1: `3fd04a385987d2fa9343e7a24e523f35d5867f21`

Blob equality proves byte identity of these files, not complete executable runtime equivalence, OS behavior or source-to-host attestation. PR47 changed other integration files; these require separate functional review.

## Physical evidence from operator, not reproduced
PR40: QUERY_IMAGE / Win32 31 first-refusal ×3, OPEN_PROCESS_MODULES / Win32 5 ×3 per phase, Registry type FAIL1, SCM type FAIL1, SERVICE_RULE_UNREVIEWED1, seven unresolved, HTTP.sys MATCH_OBSERVED, G0 FAIL_CLOSED. No PPL conclusion from error31/5. Protection/architecture NOT_COLLECTED.

## Windows Native/SCM invariants
1. Native C# P/Invoke: verify Win32 Bool/Unicode, x64 ServiceStatus and pointer-bearing ServiceConfig layout/offsets, FILETIME 64-bit, kernel SYSTEM_PROCESS_INFORMATION prefix, native handle and HGlobal finally cleanup, immediate Marshal.GetLastWin32Error on failure. No independent physical x64 runtime attestation exists here.
2. OpenProcess 0x1000 and QueryFullProcessImageNameW flags0: Win32 31 ERROR_GEN_FAILURE cannot be replaced by native-format flags1 evidence or assumed PPL. OpenProcess 0x410 module access error5 happens before PSAPI enumeration; never treat as DLL absence or grant VM_READ/SeDebug.
3. PID reuse: bind PID + creation FILETIME, kernel parent/session, before/after native and module identity, SCM membership/config, signature/hash. Unknown or contradictory evidence rejects entire diagnostic projection.
4. Reviewed contracts KeyIso, SamSs, VaultSvc, DoSvc, wscsvc use independent exact `type(x) is int and x==32` Registry and SCM checks; bool, float, 16, 0x120 are not accepted. Shared-host membership is per service member, not PID-level aggregate. ServiceDll source, mapped modules, Authenticode and paired SHA256 are mandatory evidence, not exceptions.
5. PR43 five co-occurrence buckets are diagnostic only: BOTH_FAILED, REGISTRY_ONLY_FAILED, SCM_ONLY_FAILED, NEITHER_FAILED, NOT_EVALUATED. Missing/incomplete evidence must never become NEITHER_FAILED. No new VERIFIED authorization. Rare counts can be identifying with external information; do not publish private per-member joins.

## P0/P1/P2
- **P0:** no newly confirmed VERIFIED bypass from the unchanged four Windows files; this does not certify absence of all P0 defects.
- **P1:** physical x64 ABI and protected-process behavior unverified; PR47 exact-head hosted synthetic run pending. No independent physical G0 acceptance.
- **P1:** aggregate rare-count privacy cannot be treated as anonymity. Require explicit publication policy and repeated-observation privacy review.
- **P2:** Win32 31 and ACCESS_DENIED 5 root cause unknown; type-refusal correlation in historical physical run unknown. Do not infer PPL.
- **P2:** synthetic source assertions and red/green fixtures do not constitute native runtime proof.

## CI, RED/GREEN, JUnit and evidence
PR47 hosted synthetic PR run `40203574132` QUEUED at review. CI/storage/privacy workflow results marked SKIPPED are not PASS. PR47 author reports local Windows Python3.12 1620 collected cases, 1618 PASS, 2 symlink capability SKIP, 2 live-DPAPI deselected. These are author-reported local receipts, not independently executed here. No independent exact-head JUnit digest or job artifacts established by this audit. Independent adversarial source-only tests are in separate review branch; RED/GREEN is NOT_RUN until executable CI evidence.

| Gate | Result |
| --- | --- |
| Four critical Windows files exact Git blob equality | PASS |
| PR43 per-member co-occurrence and strict int32 source review | PASS (source-only) |
| Native x64 ABI/PPL/FILETIME physical evidence | BLOCKED |
| Malformed/contradictory evidence runtime regression | BLOCKED pending independent execution |
| PR47 exact-head hosted CI/JUnit/artifacts | QUEUED / BLOCKED |
| Privacy of rare aggregates | REVIEW REQUIRED |
| Physical G0 | FAIL_CLOSED |
| G1 | NO-GO |

## Next operator-controlled read-only G0
Before any physical action: independently approve exact PR47 SHA/tree and private artifact policy, verify trusted clean checkout and Windows 11 x64 / Python3.12 / PowerShell identity, review ExecutionPolicy without forced Bypass, confirm Norton/Defender untouched and existing services/ACL/registry/firewall unchanged. Use only approved read-only commands and previously reviewed native probes with no SeDebug/PPL bypass. Keep raw SCM/member identities, paths, hashes, SIDs, DSNs and rare co-occurrence private. Record Win32 errors, before/after PID+FILETIME, parent/session, service membership, registry/SCM type and module availability; fail closed on any mismatch. Obtain independent x64 ABI witness, source-bound JUnit and hashed sanitized artifacts. Do not advance G1 without a separate authorization.
