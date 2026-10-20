# ADMINIT missing process-path inventory fix

Base: `86181d2d110688c13250a8be26b8743bcd1eb8e9`. Scope is read-only inventory and diagnostic reporting. Existing PostgreSQL, application runtime, smoke30, merge and deployment are excluded.

## Root cause

`host-facts.ps1` counted every missing WMI `ExecutablePath` as an inventory error, except a small name/PID exemption. `host_identity.py diagnose` then saved and printed the public observation before calling `safe_inventory`; its expected rejection became a second generic FAIL_CLOSED JSON with error_type ValueError. This explains the operator's report with API identity established but incomplete inventory. It was an intentional admission rejection, not evidence of corrupt DPAPI or failed MetaScalp identity.

## Evidence and admission rules

For each missing WMI path, collect private evidence without modifying processes, services, ACLs, protection, trust, or privileges:

1. `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)`, `QueryFullProcessImageNameW`, `GetProcessTimes`, and live exit status, before and after file/service verification. Match the initial CIM creation time at its microsecond resolution, and require exact equality of native before/after FILETIMEs. This rejects PID reuse, exited processes, conflicting PIDs and path changes.
2. Independently enumerate `HKLM\SYSTEM\CurrentControlSet\Services`, read-open each key, explicitly query native SCM status for every name, and query configuration for matching PIDs. Repeat after signature verification. A registry/status/config failure, changed membership or configuration makes coverage incomplete. Only SCM ERROR_SERVICE_DOES_NOT_EXIST1060 proves a registry orphan is not a registered service; AccessDenied never means absence. Successful `EnumServicesStatusEx` alone is insufficient because it silently omits services without QUERY_STATUS rights ([Microsoft documentation](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-enumservicesstatusexw)).
3. Require Valid Authenticode, reviewed publisher, stable SHA256 before/after, exact native/file/service path agreement, and no reparse point in the path. For the five reviewed services require the exact reviewed service/binary path pair; a name, PID match, or signed configured file alone cannot pass. Windows system-image fallback is limited to directly located System32 executables signed by reviewed Microsoft publishers, with proven complete service membership and no unknown attached service.
4. PID0/4 use two independent native kernel process snapshots, parent/session/creation checks and expected kernel identities. The x64 snapshot layout is sanity checked against the collector's own native process creation time. Unknown layouts fail closed. Former name-only exclusions for Registry, Secure System and Memory Compression are removed; no generic protected-process exemption is added.
5. Cross-check evidence cardinality against the original CIM missing-path PID set. Missing, duplicate or unexpected evidence cannot produce complete inventory. Grid indicators and unresolved identities block admission regardless of the reported coverage flag.

Reviewed service pairs use Windows system/program-files roots obtained from the OS, not operator-supplied paths:

| Service | Binary | Publisher |
|---|---|---|
| MDCoreSvc | Program Files/Windows Defender/MpDefenderCoreService.exe | Microsoft Windows / Windows Publisher / Corporation |
| nllbIDSAgent | Program Files/Norton/Suite/aswidsagent.exe | Gen Digital Inc. |
| Norton Antivirus | Program Files/Norton/Suite/NortonSvc.exe | Gen Digital Inc. |
| NortonWscReporter | Program Files/Norton/Suite/wsc_proxy.exe | NortonLifeLock Inc. or Gen Digital Inc. |
| SecurityHealthService | System32/SecurityHealthService.exe | Microsoft Windows / Windows Publisher / Corporation |

These paths/publishers were observed read-only on ADMINIT. They do not permit an inaccessible runtime image, an unreviewed update path, or another service using the same vendor signature. Runtime module injection and a malicious local administrator changing the collector are outside this accidental-wrong-host/conflicting-installation boundary.

## Diagnostic contract and privacy

Expected inventory refusal now emits one JSON object, writes the same public JSON, returns exit1, and includes `diagnostic_status=FAIL_CLOSED` and safe `reason_codes`. A clear observation returns exit0 with `PASS_OBSERVATION_ONLY`; it never creates authorization. Generic unexpected failures still suppress exception messages and private values. `collect-host.ps1` preserves the exit code and directs the operator to public reason codes.

Public counters distinguish `missing_process_paths`, `verified_missing_process_paths`, and remaining `unknown_process_paths`, with aggregate reason counts. Native paths, service configurations, raw creation evidence, SID/MachineGuid/hardware identity remain only in the DPAPI CurrentUser private observation. No raw private inventory is committed or uploaded as a CI artifact.

## Verification and remaining gates

Local targeted regression result before commit: 100 passed (39 new classifier/diagnostic cases plus61 existing host/authorization cases). Positive cases cover signed native Windows images, all five services, kernel identities; negative cases cover PID reuse/conflict, service replacement/membership change, missing information, unknown processes, Grid indicators, reparse points, changed files, publishers and signatures, cardinality gaps, and single sanitized JSON rejection.

`check-process-probe.ps1` exercises real read-only Windows process creation/path, SCM status/configuration/membership, kernel snapshot, and nonexistent process/service boundaries. Its CI PASS means the probe protocol behaved correctly; `scm_membership=FAIL_CLOSED_UNAVAILABLE` is an expected restricted-token refusal and is explicitly not host admission. Full Windows/Linux CI, their exact push SHA artifacts and final results are recorded in the Draft PR and delivered report; a PR synthetic merge checkout is not substituted for the candidate SHA.

The operator's elevated 16/17-process snapshot is not reproducible from the agent's more restricted token. A fresh elevated diagnose on the final immutable candidate remains required. Other protected processes or unreviewed service layouts may remain unresolved and must not be allowlisted by name. Existing TLS and dedicated-database commissioning gates are unchanged and not revalidated by this inventory-only change. No new enrollment, smoke, PostgreSQL changes, merge or deployment is performed.

Run from a new checkout of the final PR HEAD under elevated ADMINIT-JQ1IQSV\Administrator, using NEW private output paths outside the checkout:

```powershell
py -3.12 <checkout>\commissioning\host_identity.py diagnose --output <private-new-dir>\public.json --private-observation <private-new-dir>\observation.dpapi
# Check exit code and diagnostic_status/reason_codes. On refusal, stop.
# Do not use old86181d2 source manifests/enrollment to authorize changed code.
```
