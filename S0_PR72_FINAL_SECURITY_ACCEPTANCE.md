# S0 security acceptance PR72 — bounded review

Reviewed immutable PR72 HEAD 2efd6df246fd52029bf0f06d75233745dee21dd3,
tree d74480579d18a49ba6641e60962a17583c104456. PR72 is unchanged.

## Findings

P1 CONFIRMED: configured driver enumeration and status are separate processes.
An owned synthetic runner adds a new local filter driver and changes info/attributes
after enumeration, before status. On exact PR72 the callback creates its marker.
This requires a concurrent/config-changing actor; stable-config tests remain valid.
The earlier explicit TOCTOU limitation does not close this stronger acceptance scope.

No P0 demonstrated. No additional confirmed standalone helper execution is claimed.
Git status may recurse into submodules or demand promisor objects; removing status
and disabling lazy fetch narrows those paths without claiming an OS sandbox.

## Minimal correction

No status, diff, filtered hash-object, fetch, or submodule command. Retain existing
strict config enumeration refusal, but no longer rely on its driver list for safety.
Read ls-tree and ls-files stage metadata, require exact agreement, and hash tracked
raw bytes with the Git blob header in isolated Python. Reject gitlinks/symlinks,
case-fold duplicate/unsafe paths, hardlinks/reparse endpoints, missing files,
unmerged stages, untracked nonignored files and malformed/error listings.
Use --no-lazy-fetch, --no-replace-objects, explicit --work-tree, disabled fsmonitor,
hooks and pager. Unexpected inherited GIT_* variables block before any command;
only GIT_CONFIG_SYSTEM/GLOBAL/NOSYSTEM are allowed and remain reviewed inputs.
Conditional/global/system config and attribute mutations cannot dispatch a clean
or process filter through the remaining builtins.

Compatibility: raw bytes must equal Git blobs. CRLF conversion, smudged LFS,
symlinks/submodules/hardlinks are BLOCKED, not normalized or silently admitted.
At most 4 MiB listing output, 16 MiB/file, 128 MiB total tracked content, 15s
cooperative deadline; subprocess output is checked after capture, not an OS quota.
Do not repair/checkout/reset a physical repository automatically.

## Synthetic evidence

RED: immutable PR72 late-driver regression fails because an external synthetic
callback actually ran. GREEN: 86 S0 cases plus 252 existing cases = 338.
Tests include system/global/local/worktree/conditional includes, nested/macros,
process filters, malformed/truncated/oversized driver enumeration, unexpected
environment, malformed source listings, matching-index/wrong-content and error paths.
Hosted exact-head results and artifact receipts are supplied separately after commit.
Existing workflow gates preserved; the minimum increases to 338.

## S0-only operator gate

Decision for original PR72: BLOCKED under requested configuration-race threat model.
For the correction, source acceptance is bounded by actual exact-head tests/CI.
Physical S0 stays BLOCKED until an independent operator accepts:

1. Exact candidate SHA/tree and independently sourced harness reference; ordinary
   LF/raw checkout with no tracked transformations and a stable source namespace.
2. Python 3.12.10 x64 publisher/distribution, python312.dll, required stdlib modules
   and their crypto/FFI dependencies; isolated -I -S -B entry command, approved
   startup configuration and loader/CWD/PATH scope for both parent and child.
3. Actual Git executable/wrapper/core identity, authenticated distribution and
   signer match against an external approved reference, plus necessary Git DLLs
   and loader scope. Version/Authenticode Valid/self hashes are not approval.
4. Relevant configuration/include paths (including UNC access), no unapproved
   Python/runtime instrumentation, no unexplained inherited overrides, and
   independently controlled parent/source/toolchain namespace for one attempt.
5. Explicit one-S0 decision and private receipt destination; no automatic retry
   or stage chaining. Receipt is observation only, not authority attestation.

No PostgreSQL/SCM/netsh/UI/Bybit evidence is required for S0.

Residual risk: trusted Git/Python binaries still parse attacker-controlled files;
config includes may read paths, including network paths. Malicious concurrent
writers can race Python file reads or replace a loader/source namespace; two
snapshots do not prove absence of such writers or full TOCTOU resistance. No
sandbox, full native loader proof or authenticated approval receipt is created.
The source verifier does not normalize executable modes across Windows/POSIX.
Ignored untracked files retain Git ignore semantics, not full filesystem closure.

One next step: independent source review of the new Draft correction and its
exact-head hosted receipt. No physical S0 command is authorized by this report.
G0 FAIL_CLOSED, authorization NONE; S1-S4/G1 remain BLOCKED.

Primary references:
- https://git-scm.com/docs/git-ls-files (staged/other listing; no modified flag)
- https://git-scm.com/docs/git-ls-tree (raw tree metadata)
- https://git-scm.com/docs/git (--no-lazy-fetch, --no-replace-objects)
