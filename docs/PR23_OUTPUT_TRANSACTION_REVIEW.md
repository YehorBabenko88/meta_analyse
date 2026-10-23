# PR23 output/persistence adversarial review

Frozen candidate `14fc1653e7a8a347d4dd1a91148eb27e8b2c7d8c`, tree
`ebfab09dfec797b730362909846f852d0288fbcc`, base
`6601d9ef35c495de825dff1f27a8c3d186fe372b`. No source PR modification.

## Red findings and bounded correction

Four fresh tests fail on the frozen candidate: late public hardlink substitution
can truncate an existing private file; private failure plus public rewrite refusal
leaves PASS_OBSERVATION_ONLY; path-based cleanup can unlink a different record
installed at the old name; interruption before private write leaves public PASS.
The first/third are P1 preservation failures; public PASS is a P1 transaction
reporting failure, not evidence of a physical authorization bypass.

The follow-up uses exclusive `x+b` creation for every public/private output and
keeps its file object until transaction completion. Writes and erasure use that
owned handle. No rollback reopens, replaces or unlinks a user pathname. Existing
public files now cause refusal as existing private files already did; use fresh
output names. Rollback may leave an empty exclusive reservation. It must not
delete a substituted existing file merely to remove that reservation.

Public JSON always says OBSERVATION_ONLY_NOT_AUTHORIZATION. It is deliberately
not a private-write commit receipt. Only successful process completion confirms
the observed writes; a persisted report alone never authorizes enrollment or
host operations. This removes the false PASS publication window even when error
reporting fails. Existing reports are untouched and must not be treated as fresh
results from a failed invocation. Collector version advances to v5-exclusive-output;
fresh source-bound observations are required.

Private handles remain available for rollback through public writing/printing
and public close. Python cancellation is caught for owned-handle cleanup and
re-raised. Filesystem erasure/close refusal produces fixed failure diagnostics;
no raw exception text is published.

## What this does not make atomic

There is no fsync/durable atomic two-file publication. Five abrupt synthetic
child-process exits cover public create/write and private create/write/close.
They observe absent, empty or complete synthetic ciphertext depending on the
checkpoint, with no public PASS. Abrupt termination after private write can leave
complete ciphertext. A real close that closes the private handle and then raises
also prevents subsequent erasure: the after-close test observes ciphertext,
PRIVATE_CLEANUP_FAILED and neutral public JSON. Do not claim no residue for all
handled errors, power loss, controller caches or process termination.

Handle ownership protects existing inodes; it does not attest intended directory
placement under arbitrary hostile ancestor changes. Resolving a pathname is not
a directory capability on Windows. That stronger placement/durability contract
remains unproven and physical readiness remains NO-GO.

## Evidence and compatibility tests

New transaction tests cover static relative/file-symlink/hardlink aliases,
directory symlink/junction changes between precheck and create, attempted changes
after create, handled write/close/stdout faults, after-close ambiguity, abrupt
exits, a deterministic relative-path property, fresh numeric/null/array/date/
Unicode/JUnit negatives and a successful neutral-public/private control.

Windows may refuse file-symlink creation with error1314: that case is explicitly
skipped/BLOCKED without enabling privileges. Exclusive create through a junction
may itself be refused before collection; this is a conservative protection, not
proof a late alias change completed. Linux exercises the completed late parent
symlink change. The before-create swap asserts actual change independently.

The 38 prior mutation operators remain, with four new transaction operators.
Disabling the old alias precheck alone is defended by exclusive output creation.
Windows may also defend the handle-binding mutant via its exclusive/reparse or
open-handle behavior. Composite witnesses are recorded separately; these are not
direct kills. Exact counts are platform-dependent and independently verified.
Schema mutation JSON uses a fixed DEFENDED_BY_EXCLUSIVE_OUTPUT status/witness.

The same two live-DPAPI tests remain excluded. Native/database/general CI remains
skipped/BLOCKED. The approved artifact set remains source JSON, projected JUnit
and three mutation JSON files. Full identity equality and the sole allowed
Windows symlink skip must be independently checked, not inferred from minimum
counts. The pure PowerShell adapter's eight controls remain required on Windows.

No native collector, C# ABI, Add-Type, live DPAPI, PostgreSQL, ADMINIT diagnosis,
enrollment, ACL/security/service/registry changes, merge or deployment is executed.
Source/synthetic acceptance is bounded; ADMINIT remains NO-GO.
