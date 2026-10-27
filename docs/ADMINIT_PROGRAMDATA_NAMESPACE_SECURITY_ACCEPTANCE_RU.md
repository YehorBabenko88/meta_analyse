# ADMINIT — ProgramData bootstrap namespace, independent P0/P1 acceptance
Date: 2026-10-27. Review only. **PRIVATE NAMESPACE CREATE: NOT_AUTHORIZED. G1: NO-GO.**

## Exact scope and provenance
MetaAnalyse PR #60 HEAD `0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30`, tree `a85846d46df6e95f3d757e25399d991ee1db872b`. GitHub reports five successful workflows on this HEAD; none establishes ADMINIT effective ACL or physical namespace containment. Recursive tree review did not locate a MetaAnalyse-owned `DirectoryInfo.Create(DirectorySecurity)` bootstrap implementation. This report must not claim to have audited an unidentified external repository's implementation.

## Operator-supplied observations
`C:\` and `C:\ProgramData` were reported as existing directories, not reparse points, with canonical ACL. This does not establish effective access, child-object integrity, stable ancestry, or absence of attacker precreation. The observations do not include full ACE list, owner, mandatory integrity label, group attributes, privileges, access checks, or file IDs.

## P0 admission blockers (unproven, not confirmed exploit)
1. **Parent name integrity:** establish effective `FILE_DELETE_CHILD` / `DELETE`, rename and replace capabilities of every relevant principal on parent and ancestors, including inherited allow/deny ACEs, group memberships, restricted/deny-only SIDs, enabled privileges and owner rights. A child DACL does not protect its name if an attacker can replace it through parent rights.
2. **Precreation and race:** `DirectoryInfo.Create(DirectorySecurity)` must not be assumed to create a new object when the path exists; an existing object must never be accepted merely because a Create call returns without error. A separate `Test-Path` or `Get-Acl` then create is raceable.
3. **Object binding:** path-based validation must not substitute for handle-bound identity. Recheck ancestor/child file IDs and volume identity with handles, reject reparse/junction/mount-point traversal and replacement across all operations, and ensure the verified object is the one used. If robust identity cannot be maintained, fail closed.

## P1 toolchain and effective access
- Obtain pinned executable/source hashes and signatures from an independent trusted channel; never use a hash measured by the candidate as its own acceptance baseline.
- Verify x64/.NET Framework API semantics, exception behavior, inheritance and ACL creation on *new* vs *existing* directories with isolated synthetic fixtures only. Do not run on ADMINIT without separate authorization.
- Evaluate deny precedence, group attributes, integrity level, privileges, owner, inherited ACEs and effective access for the actual process token. Canonical ACL ordering is not an effective-access proof.
- An incomplete, inaccessible, malformed, or contradictory observation is `BLOCKED`, not `PASS`. A `DirectoryInfo.Create` success or self-reported ACL check is not an authorization decision.

## P2 / test design
Offline RED cases: attacker precreates directory with hostile owner/DACL; parent grants DeleteChild while child denies DELETE; ancestor junction swap between check/use; same path replaced with new file ID; inherited group allow overrides naive direct ACE interpretation; deny-only SID and privilege-enabled token; toolchain self-hash substituted; partial ACL enumeration; Create returns existing directory. GREEN requires a separate, independently measured, handle-bound and fail-closed implementation, not just a source string assertion.

## Matrix
| Gate | Status |
| --- | --- |
| PR60 exact source/tree | PASS |
| Five hosted CI workflow conclusions | PASS (hosted only) |
| Existing C:/ProgramData and no reparse at observed instant | OPERATOR-REPORTED |
| Full effective access/privileges/group/deny review | BLOCKED |
| Parent DeleteChild and ancestor replacement resistance | BLOCKED |
| Precreation and atomic object binding | BLOCKED |
| DirectoryInfo.Create(DirectorySecurity) concrete implementation | NOT_LOCATED in PR60 |
| Independent toolchain baseline | BLOCKED |
| Physical ADMINIT mutation or bootstrap | NOT_RUN / NOT_AUTHORIZED |

## Safe next step
Only read-only evidence collection after separate operator approval, using an independently pinned toolchain, with local private retention of full ACL/token/object identity. Public output should contain only fixed verdicts; no SID, paths, ACL dumps, usernames, hashes or exact object IDs. Stop on missing evidence, source mismatch, uncertain effective access, reparse/ancestor drift, existing child, unexpected privileges, or any request to change ACL/services/Defender/Norton. No private namespace creation until independent P0 closure and explicit separate authorization.
