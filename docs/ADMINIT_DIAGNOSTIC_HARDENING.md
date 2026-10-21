# ADMINIT diagnostic hardening: D1, D2, D3

Base: Draft PR #13, `65bd2e9d65b1fdd302153476b073e398130a69a3`.
This change is a separate branch/stacked Draft PR. It changes diagnostic
collection and tests only. ADMINIT remains **NO-GO**. The seven historical
conflicts are not resolved by these code changes.

## D1: retained private evidence

`host_identity.collect_facts` retains the complete returned `process_evidence`
and OS-derived `process_roots` inside `facts.private_inventory` before assessment.
The classifier's input can therefore be replayed from the private observation,
including native before/after identity, SCM before/after coverage/configuration,
signature, publisher subject, reparse result and both file hashes.

The observation uses schema 2 and DPAPI CurrentUser. Raw evidence is never
included in the public report. The internal PowerShell stdout is a private IPC
stream captured in memory by Python, not forwarded to operator stdout or logs.
Public report inventory fields are explicitly selected; raw error text is not
projected. Exceptions emit fixed safe reason codes, not exception messages.

No old DPAPI observations are migrated or rewritten. Lost evidence in the old
observation cannot be recovered. Its original collector SHA was not recorded.

## D2: precise fail-closed reasons

All failures below remain `UNRESOLVED`; no name-only exemption was added and
the service/publisher allowlist was not widened.

| Boundary | Codes |
| --- | --- |
| Native API unavailable | `NATIVE_PROCESS_API_UNAVAILABLE` |
| PID/liveness/creation | `PROCESS_ID_CONFLICT`, `PROCESS_NOT_ALIVE`, `PROCESS_CREATION_UNAVAILABLE`, `PROCESS_CREATION_CHANGED`, `CIM_CREATION_MISMATCH` |
| Native image path | `IMAGE_PATH_UNAVAILABLE`, `IMAGE_PATH_INVALID`, `IMAGE_PATH_CHANGED` |
| CIM image comparison | `CIM_IMAGE_NAME_MISMATCH`, `CIM_IMAGE_PATH_MISMATCH` |
| Signature/file | `IMAGE_SIGNATURE_UNVERIFIED`, `SIGNATURE_IMAGE_PATH_MISMATCH`, `IMAGE_PUBLISHER_UNAVAILABLE`, `IMAGE_REPARSE_UNVERIFIED`, `IMAGE_HASH_UNAVAILABLE`, `IMAGE_HASH_CHANGED` |
| SCM coverage/membership | `SERVICE_MEMBERSHIP_UNAVAILABLE`, `SERVICE_IDENTITY_UNAVAILABLE`, `SERVICE_MEMBERSHIP_CHANGED` |
| SCM snapshot changes | `SERVICE_PID_CHANGED`, `SERVICE_STATE_CHANGED`, `SERVICE_CONFIGURATION_CHANGED`, `SERVICE_EVIDENCE_CHANGED` |
| SCM stable predicate | `SERVICE_API_UNAVAILABLE`, `SERVICE_RULE_UNREVIEWED`, `SERVICE_PID_MISMATCH`, `SERVICE_NOT_RUNNING`, `SERVICE_CONFIG_PATH_INVALID`, `SERVICE_CONFIG_IMAGE_MISMATCH` |
| Reviewed service image/publisher | `SERVICE_IMAGE_NOT_REVIEWED`, `SERVICE_PUBLISHER_NOT_REVIEWED` |
| System32 image publisher | `SYSTEM_IMAGE_PUBLISHER_NOT_REVIEWED` |

The first failed predicate is returned; downstream checks must not be described
as passed when they were not reached. All raw rows remain privately available
for investigating multiple simultaneous failures. An absent CIM executable path
is the input to this classifier, not itself a native conflict. A nonempty CIM
path, if supplied, must agree with native identity.

`ReadProcess` returns structured failures instead of discarding API failure
information. It captures `Marshal.GetLastWin32Error()` immediately, before
cleanup calls, with a fixed operation stage. Failed image queries preserve
available lifetime evidence but cannot authorize a process. SCM failures also
retain operation/error and the failed service privately; incomplete membership
never means an empty service set. Neither unknown names nor valid signatures
alone establish runtime identity.

## Elevation and source provenance

Python checks the current token's `TokenElevation` through query-only Win32 APIs
before starting PowerShell. Failure to query or a non-elevated token blocks with
`ELEVATED_TOKEN_REQUIRED`; it does not attempt self-elevation. The PowerShell
collector checks enabled Administrator membership before inventory/`Add-Type`,
and Python requires its explicit elevation result as well. `safe_inventory`
also rejects absent, false or incorrectly typed elevation evidence.

Private observation metadata contains `COLLECTOR_VERSION`, verified full
candidate SHA, hashes of the actual commissioning Python/PowerShell sources,
and elevation. Source is verified before and after collection. A normal checkout
must have matching HEAD and be clean, including untracked files. A packet must
use the existing trusted manifest digest and complete executable-source checks.
Changed/unverified source or an observation from a different collector blocks.
This is an accidental wrong-source boundary, not protection against a malicious
local administrator or arbitrary replacement of the running Python process.

For a later, separately approved operator diagnostic run, from the final clean
candidate checkout under the intended elevated user:

```powershell
py -3.12 commissioning/host_identity.py diagnose --expected-sha <full-final-candidate-sha> --output <new-private-directory>/public.json --private-observation <new-private-directory>/observation.dpapi
```

For a source packet also supply `--manifest` and `--manifest-sha256`. The
`collect-host.ps1` wrapper requires `-ExpectedSha` for a clean Git checkout.
This document does not authorize executing this command on ADMINIT. The agent
does not perform a new elevated collection, enrollment or smoke30.

## D3: compiler and Norton investigation

Confirmed in repository code: loading `process-evidence.ps1` in a fresh process
uses `Add-Type -TypeDefinition` for a C# P/Invoke probe. The type-existence guard
only avoids recompilation in the same PowerShell session. `host-facts.ps1` and
the real Windows CI boundary check both load this file. A new diagnostic child
normally starts without that type.

[Microsoft's Windows PowerShell 5.1 documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/add-type?view=powershell-5.1)
states that source-based Add-Type compiles source into an assembly; loading an
existing assembly is a separate mode. In the [.NET Framework C# provider](https://github.com/microsoft/referencesource/blob/main/System/compmod/microsoft/csharp/csharpcodeprovider.cs),
`CompilerName` is `csc.exe`. `FromSourceBatch` writes temporary source files;
`FromFileBatch` allocates an output DLL even with GenerateInMemory, invokes the
compiler, reads the resulting assembly, and the compilation wrappers clean up
temporary files. Thus “in memory” does not imply no compiler process or disk
DLL. This explains a plausible compiler/temporary-file footprint, not Norton's
decision for a particular run.

[Microsoft documents CVTRES as a resource-to-object converter](https://learn.microsoft.com/en-us/windows/win32/menurc/renaming-the-compiled-resource-file).
Its reported co-occurrence is compatible with a toolchain operation; no observed
parent/child chain proving its invocation by this collector was obtained.

Operator-provided incident facts: Norton reported `IDP.HELU.PSE95`, blocked
PowerShell, terminated compiler/resource-tool processes, and removed a temporary
DLL. The reported Microsoft-valid signatures establish file signing, not the
purpose or safety of the invocation. The agent did not independently retrieve
the Norton incident record or identify that DLL's contents/hash.

Read-only local event-log inspection found accessible Application/PowerShell
logs but no matching Norton incident in Application; Security was inaccessible
to the agent's current restricted token. PowerShell script-text matches are not
process-creation proof. There is no independently verified incident timestamp,
process ancestry/command-line correlation and DLL hash tying this alert to a
particular diagnostic invocation. **Causality remains probable, unproven.**
No Add-Type compilation was retried on ADMINIT during this hardening work.

### Alternatives evaluated, not installed

| Alternative | Assessment |
| --- | --- |
| Keep the reviewed source probe | Preserves existing independent native/SCM checks; compiler/AV interaction remains a documented operator gate. Chosen for this bounded patch. |
| Prebuilt managed assembly | Removes on-host source compilation but introduces build/signature/hash/load trust and replacement races; loading still executes code subject to AV policy. Not shipped here. |
| Prebuilt native helper | Promising separate design: reproducible pinned build, authenticated manifest/hash and reviewed signer, verified launch identity and strict private IPC. Not shipped without parity evidence. |
| Change to PowerShell 7, reflection/dynamic code or rename/move compilation | Not accepted as a remedy for this detection. Different execution behavior does not prove equal identity guarantees or AV acceptance; no obfuscation/evasion workaround is introduced. |

A prospective helper must keep limited/query-only handles, runtime image and
creation-time checks before/after, PID reuse rejection, kernel-layout sanity
checks, full registry-namespace SCM coverage including unreadable services,
status/configuration consistency, stable hashes/signature/reparse protections,
and exact service/image/publisher rules. Its executable and IPC peer must also
be bound to the verified candidate, with a design addressing replacement
between verification and launch, bounded protocol parsing and fail-closed
timeouts/malformed replies. A correctly signed helper alone is insufficient.

Closing the Norton investigation requires existing private Norton history and
process/file events to be correlated locally by an authorized operator, or a
separately approved reproduction in an isolated environment. Do not restore a
quarantined DLL, disable protection, add exclusions, alter ACLs, or label the
incident a proven false positive based on signatures alone.

## Verification and remaining gates

Tests use synthetic identities/evidence only. Coverage includes native failure,
PID reuse, spoofed service binding, incomplete SCM membership, state/configuration
changes, changed hash, missing rights, retained evidence/replay, private DPAPI
round-trip/tamper on Windows and platform refusal on Linux, public redaction,
source mismatch/dirty checkout and collector changes during collection.

Windows/Linux CI explicitly checks out PR head SHA (push SHA for push events),
records actual/expected commit and tree identity, runs mandatory diagnostic tests
with a no-skip/no-failure JUnit gate, and retains existing full-suite DB/shutdown
gates. The native Windows probe executes only in the disposable hosted runner;
its PASS is not ADMINIT admission and does not evaluate Norton policy.

CI never runs host-facts/diagnose or reads a real private observation. Artifact
uploads list only public/synthetic outputs and require the privacy gate. No temp
directory, DPAPI file or raw native snapshot is uploaded. The scanner rejects
known raw-field shapes and synthetic leak sentinels without echoing contents;
it is defense in depth, not a general secret detector. Exact candidate CI runs,
counts and downloaded-artifact verification belong in the Draft PR validation
report, so results are not confused with an earlier/synthetic merge SHA.

Local full tests intentionally run without test DB DSNs. DB skips locally are
not accepted as hosted CI evidence. No ADMINIT database, service, security
setting, Grid or MetaScalp state was changed. No enrollment, smoke30, trading,
merge or deployment was performed. Fresh independent elevated host evidence
and separate operator confirmation remain required before reconsidering NO-GO.
