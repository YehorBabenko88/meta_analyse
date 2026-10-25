# PostgreSQL source acceptance, 2026-10-25

Scope: independent review of base PR47 `59626930a911c0dde330f7760c78ccd99468a1f4` (tree `5cff9cedffa5b65f3bfb351e851370ff28d7aca7`) and selected PR49 evidence `aa20ced5e0d02651a316849f764b55fed13adfc8`. This report covers source and offline tests. It does not authorize a physical host probe or certify PostgreSQL persistence, physical ownership, cancellation or disk-full behavior.

## Confirmed changes

| Severity | Source defect and evidence | Change |
| --- | --- | --- |
| P1 | Identity attestation only pinned transaction-local search_path, then exposed a connection with the role default path. Public shadow functions could affect unqualified caller SQL. A stateful fake reproduced path reset at identity commit. | Wrapper commits a separate session-level catalog pin before yielding an idle connection; witness still starts its own READ ONLY transaction. The hosted case also checks idle state and persistent session path. |
| P1 | Bootstrap SQL lacked an independently supplied system identifier and resolved identity names through session defaults before CREATE. | Fresh PGDATA file-control identity is captured before start with C locale, rejected on missing/ambiguous/noncanonical output, and matched by catalog-pinned SQL before CREATE. No physical execution was performed here. |
| P1 | `prepare-private-cluster.ps1` used Python `assert` for encrypted PGDATA/role/database binding. A pure subprocess with `-O` accepted a different data directory before the fix. | Explicit exceptions enforce binding with optimization enabled; approved port must be an exact integer. |
| P1 | Failure cleanup used `pg_ctl stop` based on `$started` and a mutable path, without a fresh system-identifier/process/physical-ownership receipt. A failed `pg_ctl -w start` can also leave a live process while `$started` remains false. | No automatic stop/delete. Failure retains the new directory and any process state for separately authorized ownership review. This intentionally does not claim cleanup completed. |
| P2 | SQL compared raw DataDir text to the expected path. .NET GetFullPath preserves a trailing separator accepted by the planner, while PostgreSQL canonicalization trims it before exporting data_directory. | Normalize only slash direction and trailing slash on both SQL operands; preserve case, path components and the independent control-file ID guard. |
| P2 | The startup log was in a shared parent directory and could append to an existing session's log. | Log is inside new PGDATA. |
| P2 | Shell and standalone provisioning SQL lacked PostgreSQL's 63-byte ASCII identifier bound; SQL also did not require identical test role/database or reject bootstrap role. | Both bounds and role/database equality now fail before CREATE. |
| P2 | Pure planner accepted UNC roots, wildcard/invalid characters and control characters. The provisioning script did not call the planner. | Local drive roots and Windows component checks run in the pre-creation encrypted-binding helper. They do not prove physical canonicalization. |
| P2 | Attestation's catalog search path is transaction-local and expires at its commit; initializer began a new writable transaction without repinning it. | Initializer and preflight pin catalog search path again in their own subsequent transaction. |
| P2 | Initializer/preflight accepted arbitrarily long connection timeouts and had no fixed statement/lock bound, allowing unbounded advisory-lock waits. | Trusted connection timeout 5 seconds, statement/lock timeout 5000 ms; caller startup options remain forbidden. |

## Rejected finding and PR49

The initial hypothesis that default PG18.1 denies dedicated roles `pg_control_system()` and `pg_control_checkpoint()` was retracted after primary-source review. No permission grants were retained. PR49's disposable test explicitly expects both privileges to be false and therefore does not demonstrate the intended viable path.

Upstream exact-tag evidence:

- [REL_18_1 pg_proc.dat](https://github.com/postgres/postgres/blob/REL_18_1/src/include/catalog/pg_proc.dat) defines these functions with default ACLs.
- [REL_18_1 system_functions.sql](https://github.com/postgres/postgres/blob/REL_18_1/src/backend/catalog/system_functions.sql) and [system_views.sql](https://github.com/postgres/postgres/blob/REL_18_1/src/backend/catalog/system_views.sql) contain no revocations for these functions.
- [REL_18_1 pg_controldata.c](https://github.com/postgres/postgres/blob/REL_18_1/src/backend/utils/misc/pg_controldata.c) contains no internal superuser check in either function.
- [PostgreSQL control-function documentation](https://www.postgresql.org/docs/18/functions-info.html#FUNCTIONS-PG-CONTROLDATA) describes observations, not a durability certificate.

`tests/test_pg18_disposable_acceptance.py` checks default EXECUTE against actual SQL rather than asserting denial. Its four cases are disabled unless explicit hosted Linux disposable mode is enabled. They require an independently supplied pg_controldata system identifier, exact loopback port55480, PG18.1, bootstrap identity and UUID-owned temporary DB/role. Container provisioning must revoke other PUBLIC CONNECT before pytest, matching the existing private bootstrap policy. Cleanup only drops this fixture's newly created DB/role after rechecking bootstrap identity and database ownership; it never stops servers or deletes filesystem paths.

## Verification and remaining gates

Latest offline command: `../venv/Scripts/python.exe -m pytest --noconftest tests/test_pg_provisioning_regressions.py tests/test_pg_cluster_attestation.py tests/test_pg_cluster_connection.py tests/test_pg_checkpoint_witness.py tests/test_pg_catalog_binding.py tests/test_pg_commissioning_binding.py tests/test_pg_cluster_plan.py tests/test_adminit_commissioning.py tests/test_pg18_disposable_acceptance.py -q --basetemp ../adminit-security-evidence/pg-green-11`.

Result: **148 passed, 4 skipped**. The four skips are the entire new real PostgreSQL suite, not evidence of SQL success. Pure regression suite has 19 cases (including the parent auditor's optimized disposable-fixture guard). Confirmed red evidence: unsafe cleanup/path contracts; initializer transaction search-path pin; optimized binding bypass (after fixing the initial subprocess import setup); both operator timeout cases; independent file-control bootstrap guards; session-level catalog path after identity commit. Initial grant regression was discarded with its invalid hypothesis.

Fully read: four `src/meta_analyse/pg_*.py` modules; commissioning initializer, preflight, prepare-private-cluster.ps1, create-test-db.sql; seven existing PG test files; `test_adminit_commissioning.py`; selected PR49 real-permissions test. Also inspected storage connection/schema and commissioning fault coverage to coordinate ownership with the parent auditor.

Independent system ID must come from the approved receipt, not the connection under test. ExpectedCluster validates its format but does not authenticate arbitrary caller assertions. SQL attestation cannot establish physical PGDATA ownership, defeat a privileged server replacement, prove Windows 8.3 aliases/junction races absent, or authorize cleanup. Fresh physical identity/ownership remains mandatory before any stop/delete. No real PostgreSQL, native inventory, service, ACL, registry or Bybit network action was executed here. No local disk-full or real-server cancellation experiment was run. PostgreSQL SQL viability remains BLOCKED until the isolated hosted suite runs without skips; physical G0/G1 remains separately BLOCKED. Process VERIFIED semantics are unchanged by this PG work.


### Windows path comparison source evidence

The general backslash-refusal hypothesis was rejected: the existing PowerShell caller already converts backslashes to forward slashes. The narrower trailing-separator defect was confirmed without a filesystem/PG probe: `.NET GetFullPath('C:\\Synthetic\\pgdata\\')` retains the final separator, while the planner accepts it. Upstream [REL_18_1 path.c](https://github.com/postgres/postgres/blob/REL_18_1/src/port/path.c) `canonicalize_path_enc()` debackslashes and trims trailing separators; `make_absolute_path()` calls it. [miscinit.c](https://github.com/postgres/postgres/blob/REL_18_1/src/backend/utils/init/miscinit.c) `SetDataDir()` calls `make_absolute_path()`. [guc.c](https://github.com/postgres/postgres/blob/REL_18_1/src/backend/utils/misc/guc.c) `SelectConfigFiles()` reflects final DataDir back into the data_directory GUC. The source regression failed before and passed after the SQL guard normalization. No SQL parser/server execution was performed here. Case folding, dot-component resolution, 8.3 aliases and ownership inference were not added.
