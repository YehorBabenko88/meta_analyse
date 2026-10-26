# PR51 hosted failures: source/fixture remediation

Base: exact PR51 `b595a3a88d32eb6e93c94bbe5d26abeacb4712de`. Separate branch; PR51 unchanged. No production module changes.

## Confirmed findings

P2: three fake-only PG test modules inherited ambient PG* variables. Exact Windows hosted image `windows-2025-vs2026` version `20261021.278.1` build script sets PGUSER/PGPASSWORD/PGBIN/PGROOT/PGDATA. Values were not read or published. Source: https://github.com/actions/runner-images/blob/win25-vs2026/20261021.278/images/windows/scripts/build/Install-PostgreSQL.ps1 . Old logs prove early PG_ENVIRONMENT_FORBIDDEN; exact individual effective runner variables were not captured, so per-variable attribution is not claimed.

Injected synthetic PGROOT on exact base reproduces all seven failed Windows identities: Store/preflight, both schema transaction cases, catalog repin and both timeout-bound cases. IndexError is secondary: early guard prevents any fake query, then the test indexes its empty call list. Expected guard/bounded-stop messages were likewise masked. Locally 7 failed/1731 passed/2 platform skips/2 deselected; actual hosted Windows was 7 failed/1733 passed/0 skips/2 deselected.

Fix: module-scoped opt-in import of per-test monkeypatch fixture in these three fake modules. Removes inherited PG* only for each fake test, restores original environment afterward. No global workflow environment clearing and no production guard relaxation. Negative Store tests add PGROOT/PGBIN/PGDATA/PGUSER and still require explicit PG_ENVIRONMENT_FORBIDDEN before connection. Other environment rejection tests remain active.

P2: Linux offscreen Qt needs dynamic EGL runtime even before rendering. Both old push/PR logs show libEGL.so.1 import errors for desktop_lifecycle and qt_diagnostics. Add libegl1 only on hosted Linux before collection; retain all Qt tests. No Linux environment is available locally; independent local Linux reproduction is BLOCKED, and actual fix must be confirmed by new hosted runs.

## Privacy / CI

Actual old Windows push/PR ZIPs downloaded through authenticated GitHub API. Independent verifier checks advertised ZIP SHA256, manifest file hashes, source SHA/tree, PR event commit parent, run/attempt/job, complete1740 identities and counters. Both have7failed cases, not PASS. Opaque projected XML contains fixed statuses and no raw error metadata. Linux artifacts absent because source-collected identity set cannot match aborted collection; no substituted fixtures.

Final gate must reject failed JUnit; failure-path projector may publish sanitized failure evidence. These are distinct operations. New suite minimum1744 includes four extra PG-environment negatives. Exact source manifest remains authoritative over minimum. Standard combined Windows/Linux workflow plus dependent disposable PG job enabled only for the new branch; legacy heavy/native jobs remain excluded. No old-SHA reruns.

Final exact SHA/tree, test results, ZIP inventory and new hosted status are in the external dated receipt/report after commit. ADMINIT G0/G1 NO-GO. No physical G0, deployment, merge or host changes.
