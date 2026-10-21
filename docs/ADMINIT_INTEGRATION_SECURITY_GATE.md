# ADMINIT cross-PR security integration gate

Base: PR #16 exact SHA e4a5c48e7155558a967868a7c8a696ab0e921dd3.

PR #17 is based on PR #14 rather than PR #16. Its strict kernel-snapshot changes and PR #16's empty/duplicate SCM safeguards must be integrated together and tested against one exact commit before any host admission. No synthetic result alone authorizes ADMINIT.

Required negative controls: empty SCM membership for lsass.exe and svchost.exe; case-insensitive duplicate SCM names; altered service PID, state, command and ServiceDll; module enumeration denied by PPL; stale or malformed kernel snapshots; PID reuse; partial native evidence; changed file hashes; private evidence in public artifacts. Every missing proof must remain UNRESOLVED.

GO requires independent exact-SHA Windows and Linux CI, a privacy review, explicit operator authorization for later real-host observation, and zero unresolved identities. No merge, deployment, Norton/ACL/service/PostgreSQL change or physical ADMINIT probe is authorized by this document.

Status: NO-GO. This document is an audit gate; the integration has passed offline CI only.

## Verified offline evidence (2026-10-21)

Exact integrated HEAD: `e4a15b1f7b5c4b75d27edb655f2b489ee2bd5bd2`.

- CI run 39670514687: Windows 979 passed, zero skipped; Linux 978 passed, one skipped; archive-pinned-contract SUCCESS.
- Kernel identity offline run 39670514937: Windows and Linux each 253 passed, two intentionally deselected (live DPAPI); JUnit completeness checks passed.
- Storage ingestion integration run 39670514708: SUCCESS.
- CI public-artifact privacy gate: passed on Windows and Linux; this does not independently prove confidentiality of host-side DPAPI evidence.

All runs are synthetic/CI evidence, not ADMINIT physical evidence. Linux CI's one skipped test and two excluded live DPAPI tests remain explicit scope limitations. No real-host PPL/VM_READ, ServiceDll memory attestation, PID reuse race, Norton interaction or ADMINIT identity has been verified. Kernel topology is not proof of arbitrary kernel identity. Status remains **NO-GO**. No merge/deployment authorized.
