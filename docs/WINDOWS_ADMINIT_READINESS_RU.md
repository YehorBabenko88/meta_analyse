# WINDOWS_ADMINIT_READINESS_RU — GPT-1 independent security audit (2026-10-25)

## Decision
**G0: BLOCKED pending operator authorization and verified host evidence. G1: NO-GO.** This document is a source-only audit, **not** a claim of physical ADMINIT testing. No antivirus, Defender, Norton, ACL, registry, service, firewall, or process changes are authorized. Do not execute commissioning G1.

## Exact source identities and CI
- PR #30 privacy: `6d01bf3d9f4118ac336624c9986c4ed876edd445` (tree `d9d20ddb7f5979816d6de4cbf6819fcaef19bf2d`). Hosted workflows queued at review; no PASS claim.
- PR #31 Windows ABI: `da0fb4735d2019e0ffa8b9f796b73725272daa5f`. Workflow 40182834659 FAILURE (Ubuntu job 121137339737 failed during pytest conftest import: `ModuleNotFoundError: psycopg`; Windows job cancelled). This is an **environment/test harness failure**, not evidence of native ABI correctness or failure. Do not mark PASS.
- PR #32 ADMINIT-first: `14025716972c9e9150f8af54bb7794e400993ed2` (tree `022c5b25e0ea830ee8fd467fefddadff016e19a5`). CI queued at review.
- PR #31 is based on another audit branch and is **not included in PR #32** by ancestry. A source review across these three heads does not establish an integrated executable tree.

## Architecture reviewed
`commissioning/process-evidence.ps1` embeds a C# Add-Type native collector, using kernel32 process handles and FILETIME, psapi module enumeration, advapi32 SCM status/config, ntdll SystemProcessInformation and read-only registry. PowerShell post-processing samples process identity, service membership, ServiceDll, module paths, file signatures and SHA256 before/after. `commissioning/adminit-g0-readonly.ps1` is a separate non-invasive host/port/worktree observation script. The latter does **not** execute the native collector, authenticate ADMINIT hardware, or establish trust in an installed PG cluster.

## P0/P1/P2 findings
- **P1 / CI blocker (confirmed):** PR #31's isolated source-only workflow installs pytest alone while repository-wide `tests/conftest.py` imports psycopg. Ubuntu exact-head job fails before tests execute. Remedy in a separate review branch: invoke a self-contained source-only unittest script outside the tests/ conftest discovery tree, or install the pinned full test dependencies. Do not misreport pytest collection as native test FAIL.
- **P1 / integration blocker:** PR #32 targets PR #30 source identity; PR #31 is not inherited. The Windows ABI correction must be independently reconciled into an isolated integration candidate with exact SHA/tree, not cherry-picked blindly.
- **P1 / native ABI not attested:** C# sequential `ServiceStatus` (nine uints) and pointer-bearing `ServiceConfig` require runtime x64 `Marshal.SizeOf` and `Marshal.OffsetOf` witnesses against Windows SDK layouts. Native `SYSTEM_PROCESS_INFORMATION` hard-coded offsets 32/56/64/80/88/100 require versioned x64 layout checks. Self PID + creation time cross-check is a defense, not a complete proof of ABI compatibility.
- **P1 / privileged process identity:** `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)`, `QueryFullProcessImageNameW`, `GetProcessTimes`, and `GetExitCodeProcess` may fail for PPL. Win32 error 31 fallback is diagnostic only; it cannot establish VERIFIED. VM_READ (`0x410`) module enumeration may be denied. Treat missing/incomplete modules, services, signature, or identity as UNKNOWN/BLOCKED, not benign absence. Never elevate SeDebugPrivilege or bypass PPL.
- **P1 / race and replacement:** PID alone is not identity. Require PID + creation FILETIME + independent kernel snapshot + path/signature/hash + stable service bindings before/after. A two-hash match does not prove no intervening file replacement or malicious mutable directory. Require stable ownership and explicit residual TOCTOU risk.
- **P2 / service coverage:** registry namespace enumeration plus SCM `QueryServiceStatusEx` can fail on inaccessible keys, orphan entries, or changes between reads. Complete coverage is mandatory before trusted conclusions. `QueryServiceConfig` size probe must reject anything except error 122 and a bounded positive required size.
- **P2 / ServiceDll and signatures:** verify root vs Parameters ServiceDll ambiguity, expandable paths, module correspondence, Authenticode trust chain and SHA256; a signed DLL alone does not prove authorized service membership. Hashes, private paths and host identifiers must not leak to public CI artifacts.
- **P2 / host readiness:** Windows 11 build/architecture, Python 3.12 executable, PowerShell edition/version, .NET runtime, admin token, process conflicts, ports 5432/55432/55480, installed PostgreSQL services, disk capacity and repository cleanliness remain unobserved on physical ADMINIT.

## Static PASS/FAIL/BLOCKED matrix
| Gate | Verdict | Evidence |
| --- | --- | --- |
| Source files PR #30/#31/#32 inspected | PASS | GitHub source at exact heads |
| QueryServiceConfig NULL-size probe requires ERROR_INSUFFICIENT_BUFFER (122) | PASS (source-only) | PR #31 process-evidence.ps1 |
| Handle cleanup paths for process, SCM and allocation | PASS (source-only) | finally blocks; runtime fault injection pending |
| PR #31 isolated CI | FAIL | run 40182834659; missing psycopg during conftest import |
| Native x64 layout offsets, FILETIME and P/Invoke runtime | BLOCKED | No Windows runtime ABI witness |
| LSASS / svchost never falsely VERIFIED | BLOCKED | No independent adversarial end-to-end negative evidence |
| ADMINIT G0 host observations | NOT_RUN | No physical host execution |
| Combined PR #30/#31/#32 exact-head CI | BLOCKED | No integrated candidate |
| G1 authorization | NO-GO | Requires separate approval |

## Safe operator-run G0, read-only only
1. Verify ADMINIT machine and intended account out of band; preserve private output locally. Confirm Windows 11 x64, Python 3.12, PowerShell version, Git HEAD/tree and clean worktree using read-only commands. Do not use execution-policy bypass.
2. Review the source of `commissioning/adminit-g0-readonly.ps1` against the exact approved candidate and execute it **only** if separately authorized as G0. It observes PostgreSQL service names/states, listening ports and MetaScalp process count. `OBSERVATION_ONLY` is not authorization.
3. Never execute native Add-Type/VM_READ probes on protected processes without explicit scope approval. Do not publish full JSON, SIDs, paths, command lines, DSNs or registry exports.
4. Stop on source mismatch, dirty worktree, occupied test port, unknown process/service binding, signature ambiguity, access denied/PPL, non-loopback test PG or unresolved privacy exposure.

## G1 acceptance and negative-test plan
G1 requires independently approved combined exact-head candidate; successful Node/Python/Windows matrix with no skipped-as-PASS; verified x64 Marshal size/offset witnesses and failure paths for each native call; PPL/access denied/error31/VM_READ refusal treated fail-closed; synthetic PID reuse, file replacement, SCM mutation, ServiceDll ambiguity, module enumeration races, invalid FILETIME, partial registry enumeration and malicious-but-signed binary negative tests; bounded private evidence with no raw public leaks; authenticated isolated PG cluster identity and cleanup plan; explicit operator sign-off. G1 must not be started from this report.
