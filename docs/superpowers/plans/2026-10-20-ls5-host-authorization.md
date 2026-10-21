# LS5-specific commissioning guard plan —2026-10-20

User authorizes read-only diagnosis and preparation, never an automatic smoke run or changes to existing services/cluster. Existing app architecture and mandatory CI gates remain.

- Recover446c72b guards; independently inspect actual Grid/PostgreSQL/MetaScalp state without public raw identifiers.
- Add stdlib host-identity module plus readonly PowerShell facts collector. MachineGuid, Windows install identity, hardware identity and userSID are private inputs; public output only salted fingerprint. DPAPI CurrentUser enrollment binds explicit operator approval, exact candidate/manifest, endpoint and session, expires, and requires fresh Grid/environment checks. No ignore-host flag.
- Strengthen manifest digest/coverage and application preflight. Launcher reruns identity,Grid,credentials,isolatedPG18 role/DB grants,MetaScalp signature/API and verified TLS before Qt. Prepare-environment and observer use same identity gate.
- Add independent negative regressions before minimal implementation; retain11PG+5shutdown gates and exact67 lifecycle count.
- Prepare commands/SQL for a new loopback-only PostgreSQL18 cluster, never existing cluster changes. PUBLIC CONNECT grants must be removed only in that new cluster and then verified for test role.
- Freeze new code SHA; run Windows/Linux/PG18 CI and fault tests; create source/evidence manifests and verified packet; update public redacted reports and PR12.
- Actual LS5 Grid footprint/incomplete coverage, no authenticated PG grants and inactive MetaScalp API retain NO-GO. Do not enroll or start smoke automatically.
