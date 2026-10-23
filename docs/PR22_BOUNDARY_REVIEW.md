# PR22 independent evidence-boundary acceptance

Frozen candidate: `6601d9ef35c495de825dff1f27a8c3d186fe372b`, tree
`65701bc435ce92c62ff417e2d66300fb2119d3d5`, base
`5f3c4bfc05fdd8cfd26fada9282ed765069011a4`. The source PR is unchanged.

## Proven findings and minimal follow-up

* P1: diagnose public output could overwrite the existing private observation
  when paths were identical or hardlinked. Exclusive private creation then failed
  and the exception-path public write overwrote it again. Check resolved paths
  and existing-file identity before collection; never write the public path when
  that check has not established separation. This protects accidental aliasing,
  not hostile filesystem replacement by a local administrator.
* P2: the service-argument ASCII check ran on already casefolded/split tokens.
  Long-s became ASCII and Unicode whitespace disappeared. Check the original
  argument substring in raw registry, expanded registry and SCM commands before
  normalization. Keep the existing command parser and reviewed contract rules.
* P2: JUnit projection ignored suite/root errors, contradictory declared counts
  and multiple testcase status elements. Validate structure and all supplied
  counters before projection; preserve a single explicit testcase status and the
  documented full-name SHA256 identity. Reject errors that cannot be represented
  faithfully. Metadata payloads may not hide nested test/status records.

`tests/test_pr22_boundary.py` reproduces these findings on frozen PR22: 17 failed,
4 passed. All 21 cases pass in the follow-up. The unchanged positive parameter/
status checks establish that failure, error and skip states remain visible.

## PowerShell producer conformance

`scripts/check_powershell_serialization_contract.py --shell powershell` extracts
only `Get-MissingProcessEvidence` plus the exact CIM Select-Object expression.
Every native call, signature/config provider, filesystem existence test and
environment-derived root is replaced by synthetic data. It never dot-sources
the collector, executes Add-Type, queries CIM/registry, uses DPAPI or accesses PG.
Inline execution does not change an execution-policy setting.

Eight positive cases exercise Windows PowerShell's real function/projection/JSON
adapter: all five service contracts, ordinary image, native 100ns detail within a
CIM microsecond, PID0 null date/FILETIME0. Source uint32 PID fields and UTC DateTime
are real PowerShell/.NET scalar types. Native/SCM/module providers are deserialized
PSCustomObject fixtures; actual C# public-field instance serialization and native
runtime behavior are not executed. Static C# field/default inspection supports
compatibility separately. Native-format success defaults and SCM diagnostics
match the schema; optional implementation/module groups are emitted together.

No systematic rejection was reproduced for those positive shapes. A missing
creation date for a nonzero PID intentionally blocks source binding, including
visible-image rows. Its frequency on real Windows is unmeasured. Unknown registry
expansions, non-reviewed service configurations, PPL access failure and changed
snapshots intentionally remain unresolved, never fallback admission.

## Validation and limits

The synthetic workflow runs eleven suites under the existing collection/DPAPI/PG
tripwires, excludes the same two real-DPAPI cases, and adds the pure PowerShell
adapter check on Windows. Three mutation scripts now cover 38 operators: 27 direct
kills and 11 separately schema-defended composite witnesses; no survivors.
Approved uploads remain source JSON, projected JUnit and three mutation JSONs.
Independent acceptance must compare the complete collected identity set, not
only the workflow's minimum-count gate. General/database CI is skipped/BLOCKED.

Private save remains exclusive direct-file creation with handled partial-write
cleanup and later-failure rollback. This is **not a crash-atomic durable
transaction**: no fsync/atomic publication or power-loss test is claimed. A process
termination may leave an incomplete encrypted file; load/DPAPI fails closed.
Filesystem refusal can prevent cleanup and is reported by the fixed
PRIVATE_CLEANUP_FAILED diagnostic. Existing records are preserved on ordinary
collisions and the newly covered public/private aliases. These limits must not
be represented as guaranteed absence of residue under all physical failures.

Source/synthetic verification does not establish real C# ABI/marshalling,
PSAPI/PPL/VM_READ access, real registry/SCM/module coherence, independent kernel
identity, physical ADMINIT authorization, DPAPI or PostgreSQL operation. No native
collector, enrollment, real-host diagnose, merge or deployment is performed.
ADMINIT remains NO-GO.
