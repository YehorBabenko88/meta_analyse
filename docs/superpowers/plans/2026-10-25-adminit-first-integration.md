# ADMINIT-first preparation after a blocked G0

**Goal:** integrate #30/#31/#32 in a separate reviewable branch, repair the proven source-only CI failure, and provide a controlled G0-to-G5 remediation plan without physical setup.

**Architecture:** #32 is the base and already contains exact #30. Cherry-pick the three #31 commits without rewriting source branches. Keep the existing application and PostgreSQL contracts. A failed G0 is a physical stop, not permission to bypass execution policy.

**Scope:** the user's detailed stage specification and autonomous safe defaults govern this preparation. G1 remains separately authorized only after complete G0 PASS. No service, ACL, AV, firewall, Grid, existing PG5432, production deployment or trading changes.

- [x] Verify current source heads/trees/merge bases and CI metadata.
- [x] Confirm local Windows/ADMINIT label privately, observe elevation without escalating.
- [x] Attempt exact #32 G0 under Windows PowerShell without policy bypass; preserve private refusal and stop physical work.
- [x] Integrate #31's API-size refusal and source tests.
- [ ] Reproduce source CI collection failure; test the workflow's dependency isolation and gated public JUnit before fixing it.
- [ ] Remove G0's implicit historical defaults, require expected tree, and prevent failed listener discovery being reported as a free port. Test source contracts without running the collector.
- [ ] Run targeted synthetic tests and actionlint; retain raw local JUnit privately and export only minimal projection.
- [ ] Create a separate Draft PR; record exact final SHA/tree and actual CI states, never substituting earlier SHA results.
- [ ] Write ADMINIT_DEPLOYMENT_AND_ACCEPTANCE_RU.md with P0/P1/P2, explicit NOT_RUN/BLOCKED and operator remediation/G1 plan.

## Review focus

Missing listener results must not mean free port. Checkout SHA alone must not mean correct tree/clean state. Successful static tests must not mean x64 ABI/runtime proof. A source-only workflow must not import live fixture dependencies. Public evidence must use the existing fail-closed publisher. No step advances stages or installs anything after the observed execution-policy refusal.
