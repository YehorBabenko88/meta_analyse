# Repository and CI hygiene — 2026-10-23

Scope: maintenance only. Base is Draft PR #24 exact HEAD `95bb4efc635fa3ddee6c8a95b43ba9a3040fffbb`. This branch is **not** a replacement for #24 and does not authorize merging, deployment, native collection, or ADMINIT work.

## Inventory at audit time

- 26 GitHub branches; 20 open pull requests (19 Draft). The #18–#24 identity chain is intentionally preserved.
- The default `main` tree is a README-only baseline; do not merge or prune branches based on the apparent difference in file counts.
- `.github/workflows/ci.yml` and `storage-ingestion.yml` explicitly exclude the identity PR branch stack, so a SKIPPED run is not a full CI PASS.
- `kernel-identity-offline.yml` is synthetic-only and does not prove native ABI, DPAPI, PPL/VM_READ, PostgreSQL, or physical acceptance.
- `commissioning-postgres18.yml` is restricted to push events on `audit/**`; it is not an exact-candidate PostgreSQL gate for PR #24.
- The PostgreSQL18 workflow uses `postgres:18.1` and exact server version `180001`. Any future image update must be separately reviewed, pinned, and evidenced.
- As checked on 2026-10-23, exact #24 runs 39918425152 and 39918431105 were QUEUED; CI runs 39918425155 and 39918431024 and storage 39918431034 were SKIPPED. Queued and skipped are **BLOCKED** for acceptance.

## Required gates (no promotion across boundaries)

| Gate | Evidence | Interpretation |
|---|---|---|
| Source identity | exact full commit and tree SHA, checked-out workflow source | Mismatch = FAIL |
| Offline synthetic | both Windows and Linux, push and PR, JUnit identities, mutation receipts, privacy projection | PASS only for synthetic scope |
| Main CI | full Windows/Linux, native read-only runner probes where specifically approved, archive and shutdown regressions | SKIPPED = BLOCKED |
| PostgreSQL | disposable PG18 exact candidate, version, JUnit, lifecycle, no unexpected skips | NOT_RUN = BLOCKED |
| Native ABI | separately approved disposable Windows host, C# layout and protected-process refusal | NOT_RUN = BLOCKED |
| ADMINIT physical | separate owner authorization, custody, environment, no live writes until explicitly approved | NO-GO |

## Safe maintenance sequence

1. Keep all open Draft PRs and evidence unchanged. Do not delete historical branches, squash evidence, or merge.
2. Record each workflow's status for the **same exact SHA**. A successful job on an older SHA is not transferable.
3. Inspect branch/path trigger predicates separately from job-level `if`. Explicit exclusions are policy, not a red-test repair.
4. Refactor repeated exclusion predicates only in a dedicated follow-up PR with before/after trigger and job-selection equivalence tests; do not enable native jobs as a side effect.
5. Introduce exact-candidate disposable PostgreSQL/native workflows only after defining runner isolation and permissions. Never use ADMINIT as a runner.
6. Review output-transaction behavior of #24 separately: success semantics, private/public reservation, crash consistency and TOCTOU; current synthetic A/B fixes do not prove crash durability.
7. Require an independent final review before selecting an integration candidate.

## Review invariants

- `SUCCESS` applies to a completed job on the expected SHA only; `SKIPPED`, `QUEUED`, `CANCELLED`, missing artifacts, or absent workflow are not PASS.
- A complete synthetic suite never promotes native or physical readiness.
- No external machine, protected process, service, ACL, Norton, PostgreSQL, or trading state may be changed by maintenance.
- A failed or incomplete public diagnostic observation must not authorize enrollment; consumer must validate private evidence.

This document is an inventory and acceptance plan, not a claim that full CI has run.

## Read-only workflow inventory CLI

`python scripts/audit_workflow_run_states.py --runs-json runs.json --sha <full-40-char-sha>` emits an inventory and exits 0 on valid input, **not** a CI PASS. To enforce an explicitly required gate, add `--require-gate 'Kernel identity offline:push'` (repeat as needed). The caller must define applicable required gates; path/branch-triggered workflows cannot be inferred from the run list alone. An absent run is `NOT_RUN`, never `PASS`. The tool does not determine native or physical authorization.
