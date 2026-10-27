# PR66 — Independent Windows Effective Access Security Acceptance
2026-10-27. No physical ADMINIT execution. Target PR66 HEAD `419d336480d9ec3b40a8bc96a402874f434cc3c5`, tree `8df68ea118c45f9aa7f8f85770e0196f98d646c0`, base `d45d9a0d21aa99cffb820c1247d45551b747c289`.

## Verdict
**READ-ONLY PHYSICAL RUN: BLOCKED pending independent ABI and toolchain review. PRIVATE NAMESPACE CREATION: NOT_AUTHORIZED. G1 NO-GO.** Hosted G0 access/provenance synthetic and CI are SUCCESS at PR66 exact HEAD; skipped other workflows are not PASS. Source-only success is not a real AccessCheck witness.

## ABI and token review
- `TokenStats` field sequence LUID/LUID/int64/DWORD×6/LUID is consistent with TOKEN_STATISTICS; FileInfo uses DWORD and three FILETIME fields with expected BY_HANDLE_FILE_INFORMATION order; Mapping uses four DWORD fields. However no independent runtime x64 `sizeof`/`offsetof` witness on ADMINIT. Fail closed on mismatch.
- `OpenThreadToken` checks impersonation only at start. **P1 coverage gap:** a thread token introduced/changed later is not sampled at the final boundary. Process primary token identity is sampled before/after, but does not prove effective thread context throughout. No claim of malicious exploit; fail closed until final thread-token check and native adversarial tests.
- `DuplicateToken` creates an impersonation token for `AccessCheck`; Windows group/deny-only and privileges are evaluated by the OS for that token. This does **not** evaluate other principals, inherited rename opportunities or future tokens.
- `AccessCheck` calls with `GENERIC_MAPPING` and bounded privilege set; boolean access granted for selected masks is a point-in-time current-token result, not a complete authorization proof. Need independent Windows x64 check of privilege buffer, status, granted mask and error paths. No elevation or AdjustTokenPrivileges permitted.
- `GetSecurityInfo` requests owner/group/DACL and returns allocated descriptor to be released with `LocalFree`. Source invokes `LocalFree` and `CloseHandle` but does not check their return values; resource-cleanup errors must not become evidence PASS. File handles use no FILE_SHARE_DELETE but ancestor and path replacement TOCTOU remain outside a complete proof.

## Confirmed P1 provenance semantics gap
`verify_manifest` validates that `authority_sha256` has 64 lowercase hex characters, but **never compares or authenticates its value**. The `basis` enum is only syntax-validated; no Authenticode/catalog/distribution verification is performed. A manifest digest supplied as a CLI argument is not, by itself, independent authority. Current output `APPROVED_MANIFEST_BYTES_MATCH` is only byte consistency under a caller-supplied digest, not approved signer or loader provenance. Existing `loader_scope=INDEPENDENT_REVIEW_REQUIRED` and `readiness=BLOCKED` correctly prevent promotion. Do not remove these safeguards.

## Physical identity / TOCTOU
Directory handles and FileInfo identity are sampled twice, token identity compared, reparse flag rejected. This reduces drift but does not prove all ancestor objects or reparse transitions were stable across path resolution. File ID match is not a full anti-rename/anti-replacement proof. Parent DeleteChild, deny ACE, inherited rights, owner/privilege and other-subject effective access remain unverified.

## Privacy and missing evidence
Public result uses fixed status enums, selected current-token right booleans, no SID/paths/token IDs or raw SD bytes. A rare combination of rights can fingerprint the host; keep full evidence local. `project_access` rejects missing fields, altered snapshots and wrong types; still only validates self-reported structures, not their origin. No `PASS` or authorization should be inferred from `CURRENT_TOKEN_DESCRIPTOR_CHECKED`.

## P0/P1/P2 and matrix
| Gate | Result |
| --- | --- |
| Exact HEAD/tree | PASS |
| Synthetic CI workflow conclusions | PASS (hosted only) |
| ABI layout x64 physical witness | BLOCKED |
| Current token AccessCheck source semantics | PARTIAL source-only |
| Other-subject access | NOT_EVALUATED |
| Manifest independent authority | BLOCKED / P1 |
| Thread impersonation drift | BLOCKED / P1 |
| Ancestor replacement/DeleteChild/TOCTOU | BLOCKED / P1 |
| Fail-closed CLI/readiness | PASS source-only |
| Private namespace create | NOT_AUTHORIZED |

P0: no proven unauthorized namespace creation or VERIFIED promotion in this source. P1: unverified authority and thread impersonation drift; incomplete parent/ancestor rights. P2: cleanup result checking and privacy of rare rights patterns. **Stop** on any unapproved manifest, token change, failed Win32 call, incomplete descriptor, reparse/identity drift, uncertain ACL or untrusted loader. No physical actions until separate operator approval after independent ABI/toolchain gates.
