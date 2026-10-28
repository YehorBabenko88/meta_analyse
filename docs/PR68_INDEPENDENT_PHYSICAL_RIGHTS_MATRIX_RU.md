# PR68 — Independent physical effective-rights acceptance matrix
2026-10-28. **G0 PHYSICAL BLOCKED; PRIVATE NAMESPACE NOT_AUTHORIZED; G1 NO-GO.**

## Exact scope
PR68 HEAD `d63f79e3cab8c6c207afa6537535655c2291e38d`, tree `f0ec4f443f74d217bd56c0f39ce94c3688cf3bb9`. Hosted G0 access/provenance synthetic and CI SUCCESS; legacy ADMINIT synthetic SKIPPED. This is source/hosted evidence only. No physical ADMINIT execution by this auditor.

## Current-token and other-subject rights
`g0_windows_access.py` measures a duplicate of the current process primary token, checks initial/final absence of thread impersonation and stable token identity, uses GetSecurityInfo and AccessCheck for fixed rights on C:\ and C:\ProgramData. It cannot prove other-subject effective access. A thread may change impersonation transiently between checks. The actual parent security descriptor, deny/inherited ACEs, mandatory integrity control and enabled privileges require a separately authorized physical observation.

| Existing context | Required independent evidence | Status |
| --- | --- | --- |
| Current ADMINIT token | full token identity, groups (enabled/deny-only/restricted), integrity/MIC, privileges, source-bound AccessCheck | BLOCKED physical |
| Existing interactive contexts | real existing token provenance; no new logon or S4U | NOT_EVALUATED |
| Existing service identities | actual existing token and service lifetime binding, no token fabrication | NOT_EVALUATED |
| SYSTEM/Administrators | explicit effective rights including privilege and ownership effects | NOT_EVALUATED |
| CREATOR OWNER/OWNER RIGHTS | inherited effective ACE and ownership effects on a *new child* | NOT_EVALUATED |
| Unknown/concurrent writers | absence cannot be inferred from one snapshot | BLOCKED |

For every relevant context independently assess CREATE_DIRECTORY, CREATE_FILE, DELETE_CHILD on parent, DELETE, WRITE_DAC, WRITE_OWNER, WRITE_ATTRIBUTES, rename/replacement and parent ancestor rights. Generic allow-only ACL inspection is insufficient; deny ACE, inherited ACE, restricted SIDs, MIC and privileges are mandatory. No new logon, SeDebug, ACL edits or writes.

## P0/P1/P2
- P0: no confirmed new privilege escalation or unauthorized namespace creation in PR68 source; this is not proof of absence.
- P1: authority packet pinned hash is byte binding, not independently authenticated signing root; approval templates remain NOT_APPROVED. No physical ABI witness, no other-subject rights, no parent DeleteChild, no precreation/rename/ancestor replacement/concurrency proof.
- P2: AccessCheck is point-in-time; initial/final token checks do not exclude transient impersonation. File ID/SD equality does not prove a stable path graph under hostile concurrent writes.
- P2: `DirectoryInfo.Create(DirectorySecurity)` may encounter an existing child; success must not be interpreted as exclusive creation or trustworthy owner/DACL. The concrete implementation was not identified in PR68's source changes.

## RED/GREEN and admission
PR68 author reports independent synthetic RED/252 PASS and 11/11 mutants killed; exact hosted workflow conclusions SUCCESS. These are not a physical x64 ABI witness. Separate RED scenarios required before acceptance: precreated hostile child, parent DELETE_CHILD despite child deny DELETE, ancestor junction swap, path/file ID replacement, inherited group allow with deny-only token, privilege-driven access, transient impersonation, partial ACL/SD/privilege evidence, stale self-pinned manifest. GREEN requires independently authenticated toolchain, native x64 ABI, real existing-token rights, stable handle-bound object identity and no false PASS on missing evidence.

## Operator-only stop conditions
Wrong exact SHA/tree or dirty checkout, unapproved authority packet, unknown token/subject, missing group/privilege/MIC evidence, ACL/SD parse failure, precreated namespace, parent DeleteChild or ancestor replacement uncertainty, reparse/rename/identity drift, AccessCheck mismatch, cleanup failure or privacy leak. Stop without retry or privilege escalation. Do not create directory, change ACL, launch PostgreSQL or move to G1. Public reports only fixed verdicts, not raw SIDs, paths, ACLs or rare combinations.
