# Meta Analyse — Unified Release Issue #79: preliminary ownership and safety audit

> **STAGE 2 OWNER MAP SUPERSEDES THE STAGE 1 PROPOSAL BELOW (2026-11-19).** The user and MASTER #111 now designate **Math** as sole owner of ALL domain numerical algorithms, **Terminan** as sole owner of strategies/simulation/experiment controls AND UI, **Grid** as sole market data collector/store, and **Unified System** as sole installer/Gateway/supervisor. Meta Analyse may be fully consolidated/archived after cutover, not retained as an independent analytics service by default. Do not treat the old row 'Meta Analyse owns orderflow/levels computation' as operative. Source-of-truth: https://github.com/YehorBabenko88/meta_analyse/issues/79#issuecomment-7007015981 .

**Executable first cleanup:** Draft PR https://github.com/YehorBabenko88/meta_analyse/pull/81, stacked on PR #78 code, unifies duplicate SQL reads of `meta_analyse.historical_trades` without touching data or live services. No cross-repo move/deletion until owner ACK, numerical parity, consumer migration and rollback.

Date: 2026-11-19. Status: **NO_GO**. Parent: https://github.com/YehorBabenko88/unified-system/issues/111

## Verified immutable baseline
- main: `2317c79d78654d8006d99b914532a089554677da` (README only).
- 74 open PRs and 88 branches observed through GitHub REST (not a full lineage audit).
- Latest stacked research candidate: PR #78 `f3c01a23fa5baaeeeb28eb8e9397e72b5ef4d5a1`, based on PR #77 `88b45c328bfdc8131ff0c6d139fddd8b27a4050c`, based on PR #76 `2c4db055e56e36384a2661d443f9abc7b2331e90`. These are NOT merged into main.
- Git tree at PR #78 contains 949 entries, including commissioning, evidence, source, tests and workflows.
- GitHub Actions list for PR #78 shows CI success (two runs) and ADMINIT final integration synthetic skipped. This does not certify real-source, Windows, installer, security or cross-repo acceptance.

## Proposed capability ownership (requires MASTER confirmation)
| Capability | Canonical owner | Meta Analyse allowed role |
|---|---|---|
| Public Bybit history/live acquisition, instrument identity, raw market storage | Grid | Consume immutable, provenance-aware data only |
| Strategy replay, backtest, paper ledger | Strattester | Return analytical features, not strategy execution |
| General numerical and scientific kernels | Math | Call versioned Math APIs; retain only distinct domain transformations |
| Terminal charts, controls, workspace navigation | Terminan | Emit result DTOs and optional UI metadata, no independent final UI |
| Install, lifecycle, authorization, recovery | Unified System | Expose health/readiness; no independent production supervisor |
| Order flow, market structure, MetaScalp levels, market-specific signal interpretation | Meta Analyse | Own only unique verified domain algorithms |

## Candidate overlap, not yet proven duplicate symbols
1. Meta Analyse orderbook/market ingest and Grid market collector.
2. Meta Analyse scientific/level computation and Math kernels.
3. Meta Analyse chart/UI and Terminan workspaces.
4. Meta Analyse PostgreSQL commissioning and Unified installer/storage ownership.
5. Meta Analyse synthetic historical research API and Strattester experiment contract.

No code is authorized for deletion based on this list. Before migration: produce exact `file:function` pairs, behavioral comparison and deterministic parity tests.

## Target read-only contract (proposal, not implementation)
Input: `contract_version`, `instrument_id`, `venue`, `market_type`, `source`, `source_revision`, `event_time_utc`, `ingest_time_utc`, `window`, `dataset_digest`, `availability`.
Output: `algorithm_id`, `algorithm_version`, `parameters_digest`, `input_dataset_digest`, `computed_at_utc`, `levels`, `orderflow_features`, `signals`, `units`, `confidence_or_uncertainty`, `quality_flags`, `provenance`.
Reject missing lineage, unknown instrument identities, mixed synthetic/live provenance, unbounded input, non-finite values, forward-looking data and write-capable side effects. Signals are research outputs, not exchange orders.

## Preservation map
**Preserve pending audit:** all 74 PR heads, all 88 branches, source and tests on the stacked research line #76 -> #77 -> #78; order-flow and level algorithms, immutable evidence, Windows/PG security gates and CI workflow history.
**Candidate for eventual replacement only after parity:** duplicate collectors, terminal renderers, service installers, general mathematical routines, redundant data writers.
**Delete now:** nothing.

## Mandatory release blockers
- Full per-branch and PR-head symbol-level inventory, duplicate matrix and dependency lock.
- Full-history secrets scan (gitleaks/trufflehog or equivalent), binary/LFS and workflow/supply-chain inspection; redact findings.
- Independent deterministic numerical parity and causal/lookahead tests.
- Exact-head cross-repo integration with Grid, Math, Strattester and Terminan.
- Real-source historical/live continuity, physical Windows acceptance, restart/rollback, scoped data preservation.
- Independent security approval and MASTER owner sign-off.

This PR is an audit contract only; it does not implement the adapter or authorize deployment. No real orders, database mutations, mass merges, branch deletion or secret disclosure.
