# LS5 PostgreSQL preflight — 2026-10-20

**Existing service is discovered, not approved for commissioning. NO-GO for database isolation until authenticated checks pass.**

| Observation | Result |
|---|---|
| Service | postgresql-x64-18, Running |
| Binary | PostgreSQL18.6 |
| Data directory | C:/Program Files/PostgreSQL/18/data |
| Actual/configured TCP port |55432; no5432/5433 listener |
| Config listen_addresses | `*` |
| Actual sockets |0.0.0.0:55432 and [::]:55432 owned by postmaster |
| Readiness | independent loopback pg_isready accepted; this is not authentication |
| SQL/grants/roles | NOT VERIFIED; no credentials guessed, no authenticated SQL attempted |
| Configuration/service/DB changes | NONE |

Read-only rediscovery: `commissioning/postgres-discovery.ps1 -Output <PRIVATE>/postgres.json`; optional `-CheckReadiness` performs only pg_isready after rejecting implicit PG environment. It reads service/data/PID/config-selected port/listen settings and actual owner sockets. File settings/readiness do not establish loaded HBA/firewall or role privileges.

Existing private HBA observations showed SCRAM local/loopback rules, but this does not prove SQL privileges or isolation. A new nonsuperuser role does not prevent access to other databases while PUBLIC CONNECT remains. Do not globally revoke PUBLIC grants or edit HBA on the existing service cluster.

## Prepared approach, not executed

Use a NEW session directory and free port55480 for a separate loopback-only PostgreSQL18 process, using installed binaries without installing/stopping a service. Host enrollment must pass first; it currently cannot because Grid clearance is absent. No new cluster/database/role has been created by this task.

Operator commands in WINDOWS_COMMISSIONING_PLAN.md use a fresh nonexisting data directory, bootstrap role meta_commission_bootstrap, SCRAM password prompts and explicit127.0.0.1 binding. `commissioning/create-test-db.sql` refuses unless current bootstrap user, postgres database, exact data directory/port, loopback listen address and only initial template databases match. Revocations apply only inside that new cluster. Dedicated role/database names must start meta_commission_; no superuser/createdb/createrole/replication/bypassrls or memberships.

The test role's password is entered interactively, not embedded in SQL/argv/reports. Bootstrap credentials are not used by the application. Preflight verifies current/session user and DB owner, PostgreSQL18, zero excessive privileges/memberships, and zero CONNECT privilege to every other connectable database, including grants inherited through PUBLIC. It also verifies OS-observed listener/data-directory binding against private enrollment. Wrong or wildcard cluster rejects before application use.

Failure is NO-GO; do not modify the existing service as a workaround. Exact operator commands, source trust and mandatory stop points are in the plan. Full target preflight and all timed tests remain NOT RUN.
