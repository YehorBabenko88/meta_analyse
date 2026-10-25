# ADMINIT-first isolated test deployment — 2026-10-25

ADMINIT is the intended **test host**, not LS5. This supersedes the target-host assumption in older LS5 plans for this candidate only; it does not waive fail-closed identity, SCM, privacy, or PostgreSQL isolation requirements.

Candidate source: Draft PR #30 `6d01bf3d9f4118ac336624c9986c4ed876edd445` (tree `d9d20ddb7f5979816d6de4cbf6819fcaef19bf2d`). Full exact-HEAD hosted CI was queued when this plan was written. No physical execution or deployment is claimed.

## G0: read-only, operator-run

1. Confirm that the PowerShell session is on the **ADMINIT test PC** under the intended account. Confirm backup/restore arrangements and available disk space; do not publish SID, machine GUID, raw process command lines, DSNs or private reports.
2. Verify checkout exact HEAD and clean worktree; never deploy an unverified ZIP or historical PR checkout. Use a **separate directory** for the candidate; do not overwrite existing MetaScalp, PostgreSQL or Grid installations.
3. From PowerShell run `powershell.exe -NoProfile -File .\commissioning\adminit-g0-readonly.ps1 -Repo C:\MetaAnalyse-Test\git-pr13` **only after checking that Repo is the exact candidate checkout**. If execution policy blocks it, do not change machine-wide policy; use a permitted, approved signed-script path or review commands manually.
4. Review the compact JSON privately. `OBSERVATION_ONLY` is not a deployment authorization; source mismatch or occupied port is a hard stop. Verify current process/service evidence with the hardened collector only under a separately reviewed G0 authorization.
5. Keep PostgreSQL 5432 and any existing service untouched. Port 55480 is merely a candidate: free at observation time is not proof it will remain free. A new disposable PG18 cluster must have a unique owned data directory, loopback binding, dedicated role/database, verified server `system_identifier`, role/permissions and cleanup ownership **before any DDL/DML**.

## Stage gates

- **G0 read-only:** exact SHA/tree, source/worktree, Windows privilege and process/SCM evidence, TLS, existing PG ports, software identity, no unresolved Grid conflicts. No state mutation.
- **G1 isolated setup (separate explicit approval):** new directory/venv, dedicated PG18 data directory and least-privilege test role, no use of production DSN, no service install, no firewall/AV changes, no existing file overwrite. Dry-run/plan-only first.
- **G2 functional:** local UI + public Bybit REST/WebSocket, test-only collector, bounded queues, orderbook gap/reconnect and PostgreSQL checkpoint checks. No trading credentials or order placement.
- **G3 30-minute smoke:** only after G0/G1/G2 PASS; CPU/RAM/disk, stale data, reconnect, queue bounds, no data corruption, controlled shutdown and artifact privacy.
- **G4 2-hour / 24-hour:** separate operator approval after each prior gate; restart/fault injection only in isolated test processes and databases.

Stop immediately on wrong source, unresolved protected-process identity, unknown cluster/role, non-loopback test DB exposure, Grid conflict, uncontrolled writes, unbounded UNVERIFIED orderbook, failed cleanup, or leaked private evidence.

## Physical access boundary

This GitHub-only agent cannot execute PowerShell on ADMINIT. The operator must run G0 locally and provide the **sanitized** output. No merge, deployment, 30-minute smoke, or changes to Norton, Windows services, ACL, production PostgreSQL or Grid are authorized by this document.

Four independent review streams: Windows ABI (Draft #31), PostgreSQL reliability (audit branch), CI privacy/provenance (audit branch), System E2E (report pending). Keep these independent from deployment until exact-head evidence and risk ownership are reconciled.
