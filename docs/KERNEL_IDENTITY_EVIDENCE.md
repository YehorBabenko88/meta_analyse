# Kernel identity evidence: bounded offline contract

Base: `3f4185fdb61ec1bab590203161cfc8face55335a`.
Scope: C1/C2/C4, unavailable process image. No live observation is included.

## Decision and blocker

C1/C2/C4 remain **UNRESOLVED / IMAGE_PATH_UNAVAILABLE** when native
lifetime and topology evidence is coherent. They are not independently proven
kernel identities. Missing or conflicting evidence produces a more specific
UNRESOLVED refusal. Empty SCM membership, error 31, process labels, native-format
paths, subsystem values and operator-supplied kernel flags never authorize an
arbitrary process. The existing special rule for PID 0/4 is not extended.

The documented APIs provide process metadata, not an authenticated mapping from
an arbitrary process to a particular non-file kernel role. Parent/session zero
are not discriminators: ordinary processes can have these characteristics.
There is no allowed general kernel-characteristic combination in this model.
A stable label can accompany coherent evidence but cannot establish identity.

Sources:
- [NtQuerySystemInformation](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntquerysysteminformation): internal structures are version-dependent.
- [NtQueryInformationProcess](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntqueryinformationprocess): process metadata and subsystem query are not a kernel-role identity contract.
- [SUBSYSTEM_INFORMATION_TYPE](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddk/ne-ntddk-_subsystem_information_type): Win32/WSL subsystem values do not establish a particular kernel-managed identity.

Unblocking requires independently reviewed, version-bounded evidence that
distinguishes the intended non-file role from ordinary/protected/subsystem
processes, with negative controls and collector ABI validation. No such evidence
was obtained in this offline task; no new admission status is introduced.

## Contract

`process_identity.classify_missing` retains the native PID/alive/creation checks.
Native PID and error must be integers (booleans/floats are rejected), path a
string, query success a boolean, and error stage explicitly present and allowed.
Native creation before/after must agree exactly; CIM creation is compared at
its existing microsecond precision. A changed native record in the unavailable
image branch returns `NATIVE_PROCESS_EVIDENCE_CHANGED`.

For an unavailable image, both `kernel_before` and `kernel_after` must contain:

| Field | Constraint |
| --- | --- |
| pid, parent_pid, session_id | Exact integer, nonnegative signed 32-bit range |
| created | Exact integer, nonnegative signed 64-bit FILETIME range |
| name | String; stability only, never an arbitrary-PID admission rule |

Both complete snapshot dictionaries must agree, including any additional
characteristics. PID/parent/session must match the CIM row. Native PID and
creation time must match the snapshot exactly. Native creation must be positive;
the existing special idle-process zero-creation case remains restricted to its
existing PID. Missing/malformed snapshots return `KERNEL_IDENTITY_UNAVAILABLE`;
disagreement returns `KERNEL_IDENTITY_CONFLICT`. PID 0/4 now also reject malformed
types before applying their existing special identity predicates.

`process-evidence.ps1` obtains topology snapshots for ordinary PIDs through the
existing ReadKernel implementation; no new native entry point, privileges or
subsystem heuristics are added. That implementation remains x64/layout-dependent.
Unsupported/unavailable snapshots fail closed. Extra enumeration may add cost;
no runtime performance claim is made. The collector was not executed locally.

`host_identity.py` needs no policy relaxation: its existing unresolved counters
keep coverage incomplete and admission blocked. A synthetic boundary regression
checks those outcomes and excludes raw snapshots from the public report. Source
hash binding already covers changed collector/classifier files.

## Verification and privacy

The dedicated `Kernel identity offline` workflow uses an isolated environment
on Windows/Linux and only the four identity test modules. Two real Windows
DPAPI boundary tests are explicitly deselected; all selected cases must pass
without skips. Existing full CI/storage jobs are disabled only for this exact
task branch, preventing native Add-Type/probe and database provisioning during
this task. Other branches retain their existing jobs.

Only synthetic inputs are used. No live diagnose, Add-Type, host observation,
service/ACL/security configuration changes, database provisioning, smoke30,
merge or deployment is part of this work. No raw inventory or DPAPI observation
is published. JUnit is used as an internal CI gate, not uploaded as an artifact.

## PR 15 compatibility

Compared with PR #15 head `69969c983335d784cff8930c7e95ec06d56de214`.
Its native-format query fields remain diagnostics and are covered by native
before/after equality. This task does not change its new ProcessRow declarations,
P/Invoke signature, module collector or service-implementation contracts.
The additional topology collection is unconditional for ordinary PIDs rather
than dependent on error 31. When integrating, retain that coverage even if PR 15
also obtains additional error-31 snapshots. Neither branch provides an
arbitrary-PID kernel admission rule. This comparison is bounded to the cited
head; later revisions need a fresh integration check.

Offline three-way application of this patch onto that PR 15 head succeeded
without conflicts using a temporary index, not a branch merge. Exported combined
tree: `929b07573321abcba23981e5a6c1959659952298`. Identity plus PR 15 service
regressions: **293 passed, 2 deselected**. This is synthetic integration evidence,
not a native-collector execution result.

## Local result matrix

| Gate | Result | Evidence / limit |
| --- | --- | --- |
| Exact base / separate branch | PASS | Base above; parallel/adminit-kernel-identity-evidence |
| Negative regression red phase | PASS | 89 failed / 28 passed before implementation; missing-stage regression also failed before fix |
| Selected synthetic identity regressions | PASS | 250 passed, 2 deselected; JUnit gate 250 collected, 0 skipped, 0 failed |
| Full offline regression | PASS (bounded) | 899 passed, 16 skipped, 2 deselected |
| PostgreSQL-dependent cases | BLOCKED / unrun | 16 intentional skips; no database DSN/provisioning |
| Two actual DPAPI boundary cases | Excluded from final synthetic selection | No real DPAPI calls in dedicated CI selection |
| PR 15 patch integration / service regressions | PASS | Clean temporary-index application; 293 passed, 2 deselected |
| Independent arbitrary-PID kernel identity | BLOCKED | No proven role discriminator; C1/C2/C4 remain unresolved |
| Native collector / live diagnose / smoke30 | Unrun | Outside authorized scope |

Environment: isolated Python 3.12 venv with requirements.lock constraints;
`pip check` passed. Full command: `python -m pytest -q -k 'not
test_private_evidence_real_dpapi_roundtrip_or_platform_refusal and not
test_windows_dpapi_tamper_or_other_platform_fails_closed' --tb=short -ra` with
PostgreSQL test DSNs absent and Qt offscreen. No global packages were installed.
Hosted Actions outcomes and exact candidate commit are reported in the Draft PR.
