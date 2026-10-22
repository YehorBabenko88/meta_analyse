# Bounded process evidence schema review

Reviewed candidate: `5f3c4bfc05fdd8cfd26fada9282ed765069011a4` (PR #21),
base `e783ad0412dd3123f19a97f5d49812353ca4d44f` (PR #20).
This follow-up is stacked on the unchanged candidate. No merge or host acceptance.

## Reproduced findings

* P1: original CIM name/parent/session/creation and the classifier row could disagree;
  a forged System32 root was not bound to the existing host boundary.
* P1: a rejected diagnostic could still save a private observation; untyped public
  counters/reasons could cross the public projection. Output failures could leave
  a newly created observation. These are synthetic boundary failures, not evidence
  of a compromised native collector or production exploit.
* P2: raw and expanded service configuration could disagree, diagnostic fields
  could contradict success, optional proof could be malformed or orphaned, and
  full Unicode casefold could equate distinct filenames/accounts.
* P2: the pattern-only artifact gate accepted raw JUnit runner metadata and raw
  failure payloads. Public JUnit now has an explicit identity/status projection.

## Change and compatibility

The existing classifier still decides trust. A pure schema gate checks every
otherwise successful result; malformed outer inputs become fixed unresolved or
blocked results. Raw JSON rejects duplicate keys and nonfinite numbers. Original
CIM records bind to normalized FILETIME, session, parent, path and evidence row.
The collector version changes to require a fresh observation; old observations
are not evidence for this schema. No new native API, privilege or collection mode
is introduced. PowerShell changes are source-only normalized CIM projection.

The five reviewed service contracts retain their original predicates, including
SamSs's integrated-image rule and exact shared-host membership. Raw/expanded
config, module/signature, SCM and native snapshots must agree. Legacy image/
SERVICE_RULES compatibility remains explicit; optional native-format and SCM
diagnostic groups, if supplied, must be complete and consistent. Supported raw
environment expansions are SystemRoot, WinDir, SystemDrive and ProgramFiles.
Unknown expansions fail closed.

System32 binds to the existing `system_directory()` boundary. ProgramFiles
remains the collector's `GetFolderPath` input, not a second independently measured
root. Creation comparisons retain the existing microsecond precision convention.
Available CIM paths retain the original inventory policy; this schema does not
create a new missing-path proof requirement for all processes.

Private serialization validates before DPAPI or directory creation; admission
failures save nothing. Exclusive writes preserve collisions and remove partial
new files. Later output failure rolls back a newly created private record. If the
filesystem refuses cleanup, the fixed `PRIVATE_CLEANUP_FAILED` status reports that
limit; deletion cannot be guaranteed against filesystem denial. No arbitrary
exception text or evidence is included in failure output.

## Reproduction (synthetic only)

Use Python 3.12 and an isolated environment, install `.[test]` under
`requirements.lock`, then `requirements-identity-synthetic.txt` under that lock.
Set `META_ANALYSE_IDENTITY_SYNTHETIC_ONLY=1` and run the exact ten-suite command in
`.github/workflows/kernel-identity-offline.yml`. Two real-DPAPI tests are explicitly
deselected; they are not PASS. All other selected cases must have no skipped,
failed or error statuses. The environment tripwires collection, elevation probes,
DPAPI, PostgreSQL and unapproved child processes unless the test mocks them.

The eight Hypothesis properties use deterministic generation, at most 64 examples
each, no persistent example database. They complement fixed adversarial cases;
they do not exhaust the input space. Run all three mutation scripts in the same
workflow. A predicate disabled alone may remain defended by the independent
schema: report `DEFENDED_BY_SCHEMA` separately and require a composite witness,
rather than calling that a single-operator kill.

Public artifacts are exactly source JSON, projected JUnit and three bounded
mutation JSON files. JUnit parameter identities are SHA256 of the full original
case name; independent verification must compare the complete collected identity
set after applying the same documented hash, not only minimum counts. Raw logs,
tracebacks, paths, properties and runner hostname are not artifact fields. The
general CI workflow's older raw artifact policy remains outside this narrowly
scoped synthetic workflow guarantee; those jobs are skipped for this branch.

## Remaining NO-GO gates

Source/synthetic PASS does not establish service implementation identity on a
physical machine, PPL/VM_READ availability, independent kernel identity, native
ABI/structure layouts, actual ADMINIT acceptance, DPAPI operation or PostgreSQL
authorization. No native collector, live DPAPI, database, enrollment, deployment
or ADMINIT diagnose is executed by this workflow. ADMINIT remains NO-GO.
