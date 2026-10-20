# ADMINIT-JQ1IQSV commissioning contract

Scope: adapt Draft PR #12 to ADMINIT-JQ1IQSV\Administrator, never transfer LS5 authorization. No merge, deployment, trading, existing PostgreSQL changes, or automatic smoke30.

The enrollment must originate on the target Windows installation/user through DPAPI CurrentUser and a new salted HMAC identity fingerprint. Require complete fresh inventory and explicit operator flags. Candidate and packet manifest digests are mandatory. Expiry remains 24 hours, observation freshness one hour. Source integrity, installation/user identity, Grid conflicts, credentials, database isolation and verified TLS remain fail closed.

MetaScalp: exact executable C:\Users\Administrator\AppData\Local\MetaScalp\current\MetaScalp.exe, SHA256 9F55837FAFBF42B713EBE9206A23AFB39FF5FF6DE4911D676E7840AE657088DF, Valid Authenticode with Grigoryan Construct LLC publisher, exact API http://127.0.0.1:17845/ping response {"app":"MetaScalp","version":"1.0.291"}. HTTP.sys queue must exclusively attach one matching process. Bind PID and process creation time; repeat collection during preflight and before runtime terminal requests. A restart invalidates enrollment.

PostgreSQL: require server_version_num=180001. New private directory beneath LocalAppData\MetaAnalyseCommissioning, only loopback 127.0.0.1:55480, no Windows service, SCRAM, dedicated meta_commission_* database and nonprivileged role with no role memberships or access to other databases. Cluster preparation takes passwords interactively; schema initialization is explicit and separate. No command connects to port 5432 or edits its configuration.

Inventory: all visible processes/services/tasks/listeners and known Grid roots; User/Machine/Process environment names and credential indicators. Full private observation is DPAPI protected outside packet. Public report publishes counts and sanitized failures. Unknown process paths or inventory errors block enrollment. This is bounded discovery, never proof of absence across every disk or inaccessible user profile. Exclude only the specifically accounted system PowerGridForecastTask under Microsoft\Windows\Sustainability; inspect other tasks for Grid indicators.

Validation: negative and positive target-identity tests, previous authorization regression tests, actual Windows PostgreSQL18.1 full suite, required eleven PostgreSQL/five shutdown JUnit gate, ten fresh lifecycle repetitions, PowerShell parse and negative setup checks, exact-source hosted CI. Windows hosted PostgreSQL18.6 is separate evidence; Linux uses PostgreSQL18.1 with numeric runtime assertion. Do not treat a PR synthetic merge checkout or the previous archive pinned commit as the candidate SHA.

Preflight remains NO-GO until elevated inventory, fresh operator enrollment, new private cluster/role/schema, exact terminal identity, authenticated PostgreSQL18.1 and verified public REST TLS all pass. No smoke command is included in the operator preflight sequence.
