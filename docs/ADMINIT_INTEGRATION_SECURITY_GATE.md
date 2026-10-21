# ADMINIT cross-PR security integration gate

Base: PR #16 exact SHA e4a5c48e7155558a967868a7c8a696ab0e921dd3.

PR #17 is based on PR #14 rather than PR #16. Its strict kernel-snapshot changes and PR #16's empty/duplicate SCM safeguards must be integrated together and tested against one exact commit before any host admission. No synthetic result alone authorizes ADMINIT.

Required negative controls: empty SCM membership for lsass.exe and svchost.exe; case-insensitive duplicate SCM names; altered service PID, state, command and ServiceDll; module enumeration denied by PPL; stale or malformed kernel snapshots; PID reuse; partial native evidence; changed file hashes; private evidence in public artifacts. Every missing proof must remain UNRESOLVED.

GO requires independent exact-SHA Windows and Linux CI, a privacy review, explicit operator authorization for later real-host observation, and zero unresolved identities. No merge, deployment, Norton/ACL/service/PostgreSQL change or physical ADMINIT probe is authorized by this document.

Status: NO-GO. This document is an audit gate, not a completed code integration or test result.
