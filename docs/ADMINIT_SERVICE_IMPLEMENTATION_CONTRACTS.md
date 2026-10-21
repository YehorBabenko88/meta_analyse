# ADMINIT: proof-gated service contracts and image-query diagnostics

Base: PR #14 candidate `3f4185fdb61ec1bab590203161cfc8face55335a`.
This follow-up remains diagnostic/admission code only. **ADMINIT remains NO-GO.**
The six old observation cases are not declared resolved by adding code.

## Evidence and decisions

The retained DPAPI observation has three stable-lifetime image-query failures
and three process-level service-policy refusals. The latter represent five
standard service identities (three attached to one host and one to each of two
other hosts). The old observation has no service implementation/module proofs.

Local read-only registry inspection confirmed OS-relative host/configuration
relationships, including different ServiceDll locations. Two standard host
files and five implementation files passed Microsoft Authenticode, stable
SHA256 and no-reparse checks. Raw paths, hashes, SCM records and private
identifiers were not published. These point-in-time disk/configuration checks
are not contemporaneous loaded-module proof for the saved process snapshots.

The new contracts therefore add **requirements**, not name-only exemptions:

| Standard service contract | OS-relative host | Implementation | Configuration location |
| --- | --- | --- | --- |
| KeyIso | system directory / lsass.exe | keyiso.dll | Parameters / ServiceDll |
| SamSs | system directory / lsass.exe | samsrv.dll | Integrated; configured ServiceDll must be absent |
| VaultSvc | system directory / lsass.exe | vaultsvc.dll | Parameters / ServiceDll |
| DoSvc | system directory / svchost.exe | dosvc.dll | Service root / ServiceDll |
| wscsvc | system directory / svchost.exe | wscsvc.dll | Parameters / ServiceDll |

These are fixed OS-relative descriptors, not copied private absolute paths or
a policy learned from arbitrary observations. No wildcard service or general
Microsoft-signed process acceptance was introduced. Any additional unknown
attached service still blocks the entire process.

## Required proof for every new contract

1. Existing native PID/alive/creation/image/CIM checks, host signature/publisher,
   stable hash, no reparse, complete independent registry/SCM membership, and
   unchanged before/after status/configuration all remain mandatory.
2. Exact service name, RUNNING state, matching process PID and reviewed system
   host path. Native QueryServiceConfig now also records type and start account.
3. Registry configuration must be fully read and unchanged before/after. Require
   Win32 shared-process type 32, exact reviewed account, host command/arguments
   and agreement with SCM. System variables are expanded locally; private raw
   and expanded values remain in DPAPI evidence.
4. ServiceDll must be at the exact reviewed location/path, or be proven absent
   for the integrated contract. Ambiguous root + Parameters definitions,
   unsupported types, unreadable keys or conflicting values fail closed.
5. Two complete PSAPI loaded-module snapshots must bind to the same PID and
   **exact** native creation time, be alive and contain the reviewed host and
   implementation paths. The normalized complete module set must be unchanged.
   Each PSAPI snapshot also brackets enumeration by a second module-handle list.
6. The exact implementation file needs a Valid reviewed Microsoft signature,
   matching signed path, stable SHA256 and no reparse points. A signed file on
   disk alone, a configured DLL alone, or a same-basename module elsewhere is
   insufficient.

PSAPI module enumeration requires query information and VM_READ access.
AccessDenied/PPL refusal is explicitly retained as unavailable evidence. No
privilege is enabled, no protection is bypassed, and no alternative access
technique is attempted. The probe queries module metadata; it does not dump
LSA memory or read credentials. It was not executed against ADMINIT protected
processes during this work. Endpoint security may still disallow the operation;
then the service remains UNRESOLVED.

Module lists are not atomic attestation of in-memory bytes. ABA changes,
injection and a malicious local administrator are not disproved by stable
endpoint snapshots. File signatures attest the checked disk file, not every
mapped memory page. These bounds are at least as strict as the existing
file/path model, with additional module/registry proof for these new rules.

## ERROR_GEN_FAILURE (31)

The saved evidence shows success of process open/times/liveness checks, and
failure specifically in QueryFullProcessImageName(flags=0), before and after.
There is no observed PID reuse. Code31 is not ERROR_ACCESS_DENIED(5), and the
old observation cannot prove a specific ACL/PPL/Norton cause. Its system
pseudo-process labels do not establish independent kernel identity.

P/Invoke now explicitly names QueryFullProcessImageNameW, Unicode/ExactSpelling,
Win32 BOOL return and DWORD-size reference. The previous positive-size Int32
declaration was ABI-compatible for its bounded buffer; no ABI defect was
demonstrated as the cause of code31. The query-only process access is unchanged.

For code31 only, the probe records a separate PROCESS_NAME_NATIVE(flags=1)
attempt and its own error, preserving the primary error. It also captures the
existing ABI-checked independent kernel snapshots for analysis. **Neither
native-format output nor a matching kernel label authorizes these cases.**
Missing primary image identity still produces IMAGE_PATH_UNAVAILABLE. No
translation of a device path into an assumed trusted executable is performed.

Microsoft references:

- [QueryFullProcessImageNameW ABI, rights, flags and error return](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew)
- [System error codes, including 31 and 5](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--0-499-)
- [EnumProcessModulesEx requirements and mutable-list limitations](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-enumprocessmodulesex)
- [GetModuleFileNameExW access rights and limitations](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getmodulefilenameexw)
- [Added LSA protection](https://learn.microsoft.com/en-us/windows-server/security/credentials-protection-and-management/configuring-additional-lsa-protection)

## Privacy, provenance and verification

Collector version is bumped to `adminit-process-evidence-v3-service-contracts`.
Existing source/SHA/elevation and DPAPI requirements remain. The old observation
cannot authorize the changed candidate and lacks its newly required proofs.
New registry/module/signature/native-format fields stay inside retained private
process evidence; public projection is unchanged. The artifact guard recognizes
these new raw shapes too. CI never receives an ADMINIT observation.

Synthetic tests cover all five positive proof contracts, combined three-service
membership, missing/denied/changed registry and module proof, wrong accounts,
types/commands/roots/DLL locations, foreign module paths, PID reuse, exited
processes, changed image/configuration/membership, unsigned/unreviewed/reparse/
changed-hash implementation files, extra attached services, and diagnostic-only
native/kernel fallback. The real Windows boundary CI additionally exercises its
own module enumeration and registry/SCM configuration binding, with public safe
status output only. No ADMINIT Add-Type compilation is performed here.

Hosted Windows/Linux results and exact final SHA are recorded in the Draft PR.
Local full tests run without DB DSNs; local skips are not hosted evidence.

Remaining gates: fresh independent elevated evidence for the changed collector,
all module/implementation requirements for each service, and a separate proven
identity model for non-file/kernel cases. Norton causality remains unresolved;
the new code is not an AV workaround. No Norton/ACL/service/PostgreSQL/Grid
changes, enrollment, smoke30, trading, deployment or merge were performed.
