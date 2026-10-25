# G0 aggregate-only diagnostics

Base: exact PR36 e2b3469d4949e7346aaa1709620f1a0c419fcbf4. Separate branch; never change PR36. User requests useful refusal categories without private persistence or authorization.

Design: a fixed-schema in-memory observer alongside the existing collector. It receives no authority and never changes evidence or classifier results. It records snapshot validation progress, unresolved classification counts, SCM/module incompleteness and HTTP.sys ownership progress. Unknown/unreached stages remain NOT_EVALUATED, never zero/success. Only fixed strings and bounded integer counts can cross the new output boundary. A separate diagnose-aggregate command always returns FAIL_CLOSED/exit1 and never calls save_private, DPAPI, enrollment or target admission. Output uses existing exclusive NewOutput, no overwrite or raw fallback.

Child launch: retain the system Windows PowerShell binary, -NoProfile/-NonInteractive/-File, capture and fixed failure codes. Remove forced ExecutionPolicy and inherited process-level PSExecutionPolicyPreference; do not change persistent or Group Policy, switch shells, inline scripts or auto-sign. If the approved exact script chain is blocked, stop. An operator-approved signed/manifest-bound packet may be used only under its effective policy; no deployment/enrollment follows.

Steps:
- Add failing synthetic privacy/aggregate/launch tests with no native/DPAPI/PG calls.
- Implement pure allowlisted observer, instrument existing validation stages, separate CLI/wrapper parameter set.
- Add Windows/Linux Python3.12 synthetic workflow with exact source receipt and staged minimal JUnit; prevent this branch from starting native/full/PG workflows.
- Run legacy classifier/host regression tests excluding live DPAPI, new tests, privacy tests and lint.
- Review exact diff, create a separate Draft PR, verify actual exact-SHA CI/artifacts or mark BLOCKED. No physical ADMINIT execution or G1.

Limits: aggregates are diagnostic observations, not host authorization or proof of inventory completeness. They do not identify the actual ADMINIT cause without a separately authorized run. No filtering protected processes. Malicious privileged local code is outside existing collector trust boundary.
