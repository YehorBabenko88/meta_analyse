# Independent PR18 acceptance harness

Candidate is pinned to 289c414011afdd52eb7b8dab6dbfd3166c8fdbcb, tree 85af7270f78a91d987e6b4d9784339b4ae2e874d. This branch starts at main and only carries verification code. Candidate sources and PR14-18 are unchanged. Workflows check out harness and candidate separately.

Synthetic runs forbid real PowerShell collection, DPAPI and PostgreSQL. Full suites use disposable hosted PostgreSQL only. The two real DPAPI cases and read-only ABI/SCM probe run separately on a hosted Windows runner. Production, ADMINIT, services/ACL/Norton changes, enrollment, smoke30, merge, deployment and trading are prohibited.

Every mode has a complete frozen identity manifest and checks exact source before and after execution. Reports reject duplicates, omissions, failures/errors, unexpected skips and inconsistent counters. The sole declared Linux full-suite skip is the Windows-only installer test; its Windows execution remains required. Native test routing is explicit and not counted as skipped success.

Only projected junit.xml/provenance.json or controls.json are published; no raw JUnit, stdout/tracebacks, hostname, local paths, raw SCM evidence, DPAPI or temporary directories are upload paths. Negative independent probes intentionally fail the job when the pinned candidate violates a contract. Green source tests do not override those failures.

ADMINIT remains NO-GO pending separate physical acceptance and operator confirmation.
