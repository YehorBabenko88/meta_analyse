# ADMINIT_WINDOWS_FINAL_ACCEPTANCE_RU — независимая проверка GPT-1, 2026-10-25

## Решение
**G0 FAIL_CLOSED; G1 NO-GO.** Это независимый source review PR43, а не повтор физического ADMINIT. Физический результат PR40: QUERY_IMAGE/31 ×3, OPEN_PROCESS_MODULES/5 ×3 endpoints, Registry type FAIL1, SCM type FAIL1, SERVICE_RULE_UNREVIEWED1, seven unresolved assessments, protection/architecture NOT_COLLECTED. Причина Win32 31 и ACCESS_DENIED 5 не установлена. Запрещено выводить PPL из этих кодов.

## Exact refs (не переносить CI между SHA)
| PR | HEAD | tree |
| --- | --- | --- |
| #31 | da0fb4735d2019e0ffa8b9f796b73725272daa5f | 3aa3e5701780d07e36404cd9886b8454cce08aed |
| #33 | 47a727c34f6894e2f844741487bb0ac5d571cb75 | 9b0673160885b8628d1e11b3981248dcd6a23bab |
| #39 | 4a92643c00a7e4d113025e1df427d8f4850f0981 | 56d46ecedea438769b673ecbf720fd06e32567ed |
| #40 | 16f5299e1b83bb4e527563e39fd889a4f90aaffa | d80c43f9e6dd54a6e0576d1181603dded4e8a3eb |
| #41 | 5b622cc218fdf90d26164d544176dd647297fc53 | 210d69f19d3912013414e550da04594e6b7fd3f2 |
| #42 | cef0155fc1fa1a5d031908bde7f54369f34a8b55 | 574a587739f43d9736b4ba279e16daf2be51a9f6 |
| #43 | a04f132d64db0981ef93de1be8208612de08a194 | d9b0c63525bb8bc28464002e676caee5a5ce626e |

PR43 base/merge-base is PR41 HEAD `5b622cc218fdf90d26164d544176dd647297fc53`. PR42 is an independent sibling review, not inherited by PR43. Other PRs have different historical bases: their statuses do not constitute integrated exact-head acceptance.

## SCM co-occurrence source review
PR43 `config_checks` calls `service_host_configuration_checks` for each reviewed service member, computes five buckets BOTH_FAILED, REGISTRY_ONLY_FAILED, SCM_ONLY_FAILED, NEITHER_FAILED, NOT_EVALUATED. The existing helper requires `type(x) is int and x==32` independently for Registry and SCM; it is not a mask and rejects `bool`, float, own-process 16 and 0x120. The five reviewed contracts are KeyIso, SamSs, VaultSvc, DoSvc, wscsvc. Shared-host PID does not imply one member: correlation must be per service in each phase, not across PID or marginal totals. A missing/incomplete config yields NOT_EVALUATED, never NEITHER_FAILED. The two marginal FAIL1 counts do not establish a same-member failure.

**Independent oracle #42 comparison:** Both-failed-in-one-member and separate-failures-in-two-members have identical marginal totals but different five-bucket distributions. PR43's code computes buckets inside the member loop and does not reconstruct from marginals; source contract is consistent. However, independent runtime RED/GREEN against exact PR43 has not been executed in this audit; do not mark independent GREEN.

## Native security boundaries
- P/Invoke: inspect sequential ServiceStatus and pointer-aligned ServiceConfig, x64 NT process layout offsets, Win32 Bool marshaling, FILETIME creation, and all handle/free finally paths. Static review is not Windows x64 ABI attestation.
- `OpenProcess(0x1000)` and `QueryFullProcessImageNameW(flags=0)`: Win32 31 is ERROR_GEN_FAILURE, not a PPL classifier. Native-format flags1 is diagnostic, not Win32 image replacement.
- `OpenProcess(0x410)` for PSAPI: ACCESS_DENIED 5 happens before EnumProcessModulesEx; it cannot establish missing DLL, PPL, or wrong signature. Never add SeDebugPrivilege or relax VM_READ.
- PID reuse/snapshot drift: require PID+FILETIME creation, kernel snapshot parent/session binding, paired native/module times, stable SCM membership, before/after registry and module list. Unknown observations fail closed.
- SCM/Registry: strict shared-host member matching, type/account/args/image path and ServiceDll source; mapped module list, Authenticode status and SHA256 pair required. Signature alone does not prove membership. No new VERIFIED path may be introduced by diagnostic projection.

## P0/P1/P2
- **P0 confirmed:** none from reviewed PR43 delta. This is not proof of absence.
- **P1 acceptance blocker:** no independent executed adversarial comparison on PR43 exact HEAD, nor physical read-only correlation evidence. Require source/CI receipts before claims of GREEN.
- **P1 privacy risk:** five bucket counts can reveal rare member combinations with auxiliary knowledge and repeated samples. No per-member names/PIDs/paths/raw types in public output; restrict raw diagnostic output to private operator review and require separate publication approval. Aggregation is not k-anonymity.
- **P2 unresolved:** error31 and access denied 5 remain root-cause unknown; PPL and architecture NOT_COLLECTED. Physical R0–R5 counts do not establish specific failing contract.
- **P2 corrected upstream:** PR41 early native/module failure projects NOT_OBSERVED rather than default false NOT_ALIVE; runtime classification unchanged.

## RED/GREEN and CI matrix
| Gate | Result | Evidence |
| --- | --- | --- |
| Strict int32 predicates | PASS source-only | process_identity.py |
| Per-member co-occurrence vs marginal totals | PASS source-only | PR43 config_checks; independent #42 counterexample |
| PR43 local targeted synthetic | REPORTED PASS, not independently replayed | PR43 author: 337 PASS/1 capability skip |
| PR43 hosted synthetic exact HEAD | QUEUED / BLOCKED | run 40200322626 |
| PR43 unrelated CI/storage | SKIPPED, not PASS | exact HEAD workflow list |
| Independent RED/GREEN on PR43 | NOT_RUN | no independent runtime receipt |
| ADMINIT physical root cause | BLOCKED | no new authorized read-only run |
| G0/G1 | FAIL_CLOSED / NO-GO | operator observations and unchanged authorization |

## Next read-only ADMINIT admission
Approve separately an exact source HEAD/tree and signed/sanitized diagnostic schema, run only under an operator-controlled G0 scope. Capture private per-member correlation for reviewed service contracts, paired before/after lifetime, registry/SCM status, and native errors without changing privileges or services. Validate source identity and artifact hashes before/after. Do not publish rare member joins; stop on drift, unknown type, incomplete SCM, failed module access, signature/hash ambiguity or missing process. G1 requires separate authorization and independent Windows x64 ABI evidence.
