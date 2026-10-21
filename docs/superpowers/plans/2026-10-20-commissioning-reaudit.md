# Windows commissioning re-audit implementation plan

Goal: independently qualify a reproducible successor of13901274 for controlled read-only target tests.
Architecture: retain existing Qt/asyncio/storage architecture; integrate reviewed deltas into existing isolated audit worktree/PR12. Never modify developer branches or production hosts.
Spec: user commissioning re-audit request2026-10-20 and Issue11.

- [x] Recover exact baseline, manifest, four reports, raw JUnit and current immutable PR heads.
- [x] Dispatch independent read-only recovery, data and shutdown/CI investigations.
- [ ] Review and integrate PR6 TLS diagnostic and PR7 autonomous recovery deltas; explicitly retain equivalent baseline storage fixes.
- [ ] Reproduce/fix gate regression without dropping any of ten PG requirements; test exact identities, missing/duplicate/skipped cases.
- [ ] Review cancellation invalidation and original cleanup failure preservation; add independent regressions for confirmed defects before minimal changes.
- [ ] Provision PostgreSQL18 only in disposable GitHub Windows/Linux CI, verify SHA/version and run full suite, fault tests, repeat lifecycle.
- [ ] Freeze code SHA and full provenance manifest; independently parse exact-SHA JUnit/artifacts and build/hash/extract-verify target packet.
- [ ] Update commissioning audit/matrix/remediation/plan/evidence and draft PR12 with separate smoke/soak/stress decisions. Actual target tests remain NOT RUN without real logs.

Safety: no merges, deployment, external trading/MetaScalp writes, production DB, TLS bypass, warning suppression, relaxed skips or fixed-delay synchronization. Target activation requires operator approval and separate PC. Report-only head must be distinguished from tested source SHA.
