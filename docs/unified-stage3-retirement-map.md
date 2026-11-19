# Meta Analyse — Stage 3 ownership, consumers and retirement gate
2026-11-19 | Meta #79 | MASTER #111 | import graph #114 | retirement #115 | E2E #116 | NO_GO.

Baseline: Meta PR #78 source HEAD f3c01a23fa5baaeeeb28eb8e9397e72b5ef4d5a1 (not README-only main).
Meta PR #81: existing historical trade SQL query consolidated with flow_history_storage.read_flow_history.
83 Python modules under src/meta_analyse on the current stacked source; classify by function, not whole module.

## KEEP / MOVE / MERGE / DELETE proposals (no deletion authorized)
| Source (src/meta_analyse/) | Proposed target | Gate |
|---|---|---|
| core.py:untouched_levels,Minute.poc,RollingFlow.metrics/wall_score; orderflow_metrics.py:calculate; orderflow_aggregation.py:aggregate_by_time/aggregate_by_price | MOVE into existing Math kernels | Decimal precision, time availability, POC ties and negative cases |
| footprint.py:Footprint.poc/delta; footprint_engine.py:FootprintEngine.execution; tape_velocity.py:TapeVelocity.add; wall_tracker.py:WallTracker.observe | MOVE numerical calculations into Math; Grid owns raw frames | Event-time/reconnect/gap provenance, deterministic comparison |
| core.py:PaperEngine.on_trade/on_closed_minute; level_sync.py:LevelSync.replace/crossed; level_publish.py:publication_decision | MOVE into Terminan canonical strategy/level UI | Paper parity, no live orders, no deletion of foreign levels |
| desktop.py:main; desktop_service.py:DesktopService; flow_style.py:flow_cell_style; flow_diff.py:changed_rows | MOVE UI behavior into Terminan existing terminal | One UI launcher, actual browser/Windows test |
| market_collector.py:MarketCollector.start; collector.py:CollectorService.run; raw_trades.py:RawTradeStream.run; history.py:collect_history; market_store.py | MERGE only unique collector data features into Grid, then DELETE Meta writer | One writer, DB preservation, public REST/WS continuity |
| flow_history_storage.py:read_flow_history; orderflow_archive_reader.py:read_orderflow_trades | MERGE internal SQL now in Meta #81; later replace with Grid read-only snapshot and DELETE adapters | Full consumer graph, schema equivalence, retention, rollback |
| trade_archive.py:verify_archive; archive_* and bybit_archive_* and history_* | MERGE unique archive verification into Grid | Manifest/time interval/content digest parity |
| ohlcv_research_adapter.py:analyze_ohlcv_research; grid_history_adapter.py:analyze_grid_history | SPLIT: Math algorithm, Grid provenance, Unified Gateway, Terminan view | Exact contract, lookahead and digest tests |
| headless_service.py:PrivateServer,Handler,SourceVerifier,main; pg_*; recovery.py | MERGE required admission and lifecycle gates into Unified; DELETE second service after cutover | Windows SCM and PostgreSQL rights and independent security |
| analysis_session.py:AnalysisSession.start/stop; runtime.py:Runtime.run; pipeline.py | DELETE duplicate orchestration only after owner replacement | All consumers migrated, rollback and real E2E |
| Tests, evidence, user history, branches and PRs | KEEP | Preserve until all release and archival gates pass |

## Confirmed imports requiring cutover
- desktop_service.py -> AnalysisSession, BybitPublic, Runtime, FlowBridge, flow_history_storage.read_flow_history.
- analysis_session.py -> RawPipeline, MarketCollector, AnalysisCoordinator; analysis_coordinator.py -> FootprintEngine, TapeVelocity, MarketClock.
- runtime.py -> core.PaperEngine, core.RollingFlow, core.new_minute, core.floor_minute.
- ohlcv_research_adapter.py and grid_history_adapter.py -> core.Candle and core.untouched_levels.
- orderflow_archive_reader.py -> flow_history_storage.read_flow_history (single SQL reader in PR #81).
- pyproject.toml console script meta-analyse -> meta_analyse.desktop:main. HeadlessService.main is another entrypoint candidate; enumerate all callers via #114.

## Numerical differences, not equivalent until independently proven
- Meta untouched_levels uses Decimal/datetime whereas Terminan levels uses float/as_of_ms and closed-candle gates.
- Meta Minute.poc chooses by volume, distance to last close, then price; Meta Footprint.poc and Strattester volume_profile pick lowest-price ties.
- Meta orderflow_metrics.calculate tracks unknown volume as Decimal; Strattester research.orderflow.cumulative_delta uses float.

## Retirement #115 decision
NOT READY TO ARCHIVE OR DELETE. Missing target-owner ACK, full static/dynamic import inventory, exact-head CI, numerical parity, real Bybit continuity, physical Windows installer/one-Terminan acceptance, user-data migration/rollback proof and full-history secret audit. After all gates: archive read-only retaining immutable refs, then require separate explicit user confirmation naming exact repository before deletion.

## Rollback
Keep PR #78 source and all refs. PR #81 can be reverted without touching database schemas or user data. No force push, mass branch closure, backup removal or live orders.
## Stage 4 pinned Math consumer contract (not yet production cutover)
- Math Draft PR #121 pinned HEAD `7ea2eb7f4240cc50ab4e7a0084728ce15a6e22f7`, verified source blob `python/market_profile_math.py` = `13c3721ea9cab8079a8f6bfba4244c1b0a79a393`.
- Exact same-input source parity check: `scripts/check_math_consumer_parity.py` loads only that verified Math blob; `.github/workflows/ci.yml` executes the check on Windows and Linux, independently of existing mandatory suites. This test is offline source parity, not real data, not a runtime Math import or end-to-end release proof.
- Concrete Meta call graph: `core.py:Minute.add -> price_bucket`; `core.py:Minute.poc -> volume_profile_poc(profile, close=minute.close)`; `footprint.py:Footprint.add -> price_bucket`; `footprint.py:Footprint.poc -> volume_profile_poc({price: cell.buy+cell.sell})`; `footprint.py:FootprintCell.delta -> executed_volume_delta(buy,sell)`; `footprint.py:Footprint.delta` sums those deltas. `core.py:PaperEngine.on_closed_minute` consumes Minute.poc, and belongs in Terminan later.
- **Do not switch these runtime imports yet**: Math #121 now proposes a `unified-math-kernels` 0.1.0 distribution and `market_compute_api.compute_batch` v1 DTO, but it remains unmerged and has not passed full accepted install/integration E2E. Math refuses zero/nonfinite prices that legacy Meta may accept; no full real-input-domain parity or rollback evidence yet. #114 must establish installer/import path first.
- Terminan #87 `66db839eff32bc6db135eac9e978a185de4feab5` and #88 `66217c11f6fb046deba91d10dacaf1871e8b6ee7` now reportedly share one `terminan/contracts.py` registry blob, but their tests, docs, full trees and PR ancestry differ. Meta must not assume combined runtime/merge acceptance; only an owner-approved single PR with cross-branch tests and import graph #114 can unblock strategy consumer migration.
- Current PR #81 is documentation/tests plus internal SQL dedup; it neither deploys a second market service nor changes user history.


## Stage 5: hard single-owner boundaries and executable launch fence

- **Bybit/Grid only.** Legacy Meta entrypoints still reach exchange: `desktop_service.py:DesktopService.initialize` creates `exchange.BybitPublic`; `DesktopService._start_flow` calls `instruments(self.exchange)` and `AnalysisSession.start`; `collector.py:CollectorService.run` owns another BybitPublic/RawPipeline; `market_collector.py:MarketCollector.start` runs orderbook and OI collection; `raw_trades.py:RawTradeStream.run` contains direct Bybit WS. These are KEEP ONLY FOR TEST EVIDENCE until consumers switch to Grid APIs; they are **not** approved production connections.
- **One Terminan.** `desktop.py:main` now explicitly refuses obsolete Meta CLI start *before* QApplication/Window construction (test: `tests/test_desktop_flow_contract.py:test_legacy_desktop_cli_refuses_before_qt_or_exchange_start`). A direct `Window()` construction still exists for legacy isolated regression tests. This fence alone cannot disable previously deployed copies; Unified must control installation and service registration.
- **One PostgreSQL infrastructure owner (Unified).** Meta `commissioning/prepare-private-cluster.ps1`, `pg_cluster_plan.py:plan_only`, `storage.py:Store.initialize`, `storage_migrations.py`, `archive_db_import.py`, and `market_store.py` retain old cluster/schema/write paths. Distinguish infrastructure provisioning (Unified-only) from Grid market-schema ownership/writes; paper strategy result persistence -> Terminan. Do not run Meta commissioning/DB migrations in unified release. No database/table deletion yet.
- **One control plane/Gateway (Unified).** `headless_service.py:main/PrivateServer/Handler` is a second local server candidate; `analysis_session.py:AnalysisSession.start/stop` and `runtime.py:Runtime.run` are independent lifecycle candidates. Their test and provenance code must be mapped to Unified/Grid/Terminan; no second general orchestrator may survive. No direct SSH/LAN/SCM mutation was performed by this PR.
- `install.ps1` and the `meta-analyse` console script remain legacy artifacts; they are NOT the unified installer and still need dependent workflow/consumer inventory. The `meta-analyse` runtime entrypoint now fails closed, but source retention and historical installer availability remain a retirement blocker.
- **Dependency order:** Grid v1 REST/WS/provenance read API with read-only roles -> Math versioned distribution/compute API -> Terminan paper/visual API -> Unified Gateway/installer/operator scopes -> #114 consumers/import graph -> #116 physical E2E/rollback -> #115 archive review. Test and maintain all old data and branches until signed off.

## Stage 5: source-pinned installable Math compute contract under test

- Candidate Math PR #121 commit `7ea2eb7f4240cc50ab4e7a0084728ce15a6e22f7` now contains `pyproject.toml` (`unified-math-kernels==0.1.0`, blob `82876b8a6fe14cc6ddfddc6b2f3785206c82d895`) and `python/market_compute_api.py` (blob `1fc85cf71961fb3686a69ad3a9feaeb7be6fdf61`), alongside original Math kernel blob `13c3721ea9cab8079a8f6bfba4244c1b0a79a393`.
- Meta existing CI on Windows and Linux now checkouts exactly that Math commit, installs its distribution for **contract tests only**, proves import source paths resolve to the reviewed Math checkout, checks the `math.market.compute.v1` request and `math.market.result.v1` response including deterministic digest, units, Decimal, no execution authority, and refuses unauthorized requests.
- This is not a Meta runtime consumer switch, a deployed Gateway or an authenticated market-data contract. Real Grid provenance is not established by caller-supplied hash; the Math reply explicitly says `CALLER_SUPPLIED_UNATTESTED`. Source is synthetic and no exchange is contacted.
- Old Meta `core.py`/Footprint/PaperEngine remain as frozen compatibility evidence until all production consumers are switched to the installed Math package through Unified ownership and full numerical/domain parity (including zero/nonfinite price rejection) is proven.

## Stage 6: full absorption target and repository retirement decision
See docs/meta-stage6-feature-migration.csv for 17 feature families with USED/UNKNOWN/UNUSED_CANDIDATE, old function names, callers, destination owners, replacement candidates and deletion gates.
- Permanent independent Meta runtime needed: NO, provided all useful features transfer to Grid, Math, Terminan and Unified.
- Archiving Meta today: NOT_READY. Direct exchange clients, historical readers, level synchronization, paper engine, settings and specialized analytics lack complete consumer migration/acceptance.
- Deleting the Meta repository today: NOT_AUTHORIZED. Retain Git history, tags, branches, PR evidence, datasets and restore proof; separately ask owner approval naming the exact repository after acceptance.
- Distinct behaviors to preserve: LevelSync.replace touches only signature-owned MetaScalp levels; Minute.poc ties by nearest close vs Footprint.poc ties by lowest price; tape velocity and wall tracking are different microstructure models; FlowHistorySnapshot must not promote unverified history; persisted level_map, profiles, paper_fills, historical_trades and checkpoints need export/readback receipts.
- No source item is proven UNUSED across all external consumers. The obsolete desktop CLI is blocked by PR #81 but test code still imports Window; removal requires #114 static and dynamic cross-repo entrypoint scan.
- Candidate owners are Math #121, Grid #292, Terminan #87 and Unified #111; none qualifies a complete release without parity, versioned APIs, pinned provenance, actual consumer cutover, Windows/Bybit E2E, all-history secret scan and rollback.
- Deletion gate: validate every old source consumer, identical-input precision and causal behavior, user settings/history/results and DB row counts/digests, no concurrent writers or duplicate services, physical Windows release acceptance, and separate owner confirmation.

- Full pinned Python **file** inventory: `docs/meta-stage6-file-inventory.csv` contains all 83 `src/meta_analyse/*.py` modules at this Draft PR head, their exact Git blob OIDs, candidate owners, and explicit NOT_EXHAUSTIVELY_CHECKED reachability. Nine mixed-ownership modules require per-symbol separation. The 17-row feature-family ledger is `docs/meta-stage6-feature-migration.csv`. These two ledgers are not a complete dynamic/per-function audit, so archive clearance remains NO_GO.

## Stage 10: isolated headless Math dependency

- KEEP `grid_history_adapter.analyze_grid_history`, MetaScalp level ownership, historical settings and persisted result evidence pending migration.
- MOVE the headless integration launch onto Unified's explicit `--dependency-root` for the Math SDK. This lets the isolated process import `core.py -> market_profile_math` using the already pinned SDK at `98d6783522aac7155cbb4635e5b29239746d88e0`. CI retains `-I -S -B` and the existing Math source parity verification.
- MERGE through existing adapters and owner APIs. Production registration must supply the approved Math root or use the replacement Gateway route. Direct exchange/collector, paper writer and Qt/settings ownership transfers still require matching, qualified contracts and persisted row-digest/restore proof.
- DELETE no source or data. Keep the legacy paper tests as a parity oracle until Terminan accepts equivalent inputs and results.

## Stage 11: qualify the next Math cohort

Meta CI, commissioning and storage integration pin Math #122 at `150910fff08c896f243fdf7e64ec18611420a4d2`. The kernel, public compute API and package metadata Git objects match the Stage 10 pin. The parity script still verifies the same three objects and installed SDK. Unified bootstrap receives the Math source root explicitly. Revert the Stage 11 pin commit to restore the prior candidate across all four files together. This requires no data migration.

## Stage 15: offline Terminan journal delivery

`python -m meta_analyse.offline_paper_delivery SOURCE_JSON EXPECTED_SHA256 LEDGER_SQLITE`
requires the pinned Terminan SDK from #91. Retain the source file and its independently
recorded SHA-256 before attempting delivery. The `meta.paper.source.v1` object contains
`schema`, `source_id`, `symbol`, and an ordered nonempty `events` array of
`terminan.paper.event.v1` objects with contiguous sequences starting at one. Source limit
is 8 MiB. Terminan validates each event and commits its ACK and checkpoint. An interrupted
delivery can leave a committed prefix. To resume, reopen the same ledger and replay the
original file with its original hash. Do not edit a rejected or incomplete file and treat
it as a retry: content changes create a different run identity.

The delivery receipt reports the source digest, run identity, highest ACKed sequence,
fill count and ordered SHA-256 of fill ACKs. The adapter reads back the journal and rejects
a fill digest mismatch. Keep the original source and local SQLite backup for restoration.
The live monitor remains fenced. Source qualification, live cursor admission and migration
of historical PostgreSQL rows need separate evidence.

## Stage 16: reconcile the Terminan checkpoint before resuming

The adapter checks the last durable ACK against the source sequence and event hash
before submitting anything on reopen. The delivered receipt uses the checkpoint
read back from Terminan and requires the final persisted ACK to match the delivery
ACK. A divergent checkpoint fails closed. Qualification pins Terminan #91
`7b15cacb03cd51477d0d7b4254694e0db923f092` and its Math SDK dependency
`ba7a07e8a7730c7d6be328b2dfd39132274e1e8e`.

## Stage 19: refresh offline qualification pins

Meta's CI qualification ties the existing offline PaperJournal delivery and installer
to Terminan #91 4035647edb332260859850ad2a3ffc1044a4c818 and its active Math SDK pin
8de3858cd5ca9a63dc3cd10f5f5cdec870ef4440. The original source, durable ACK and fill
digest checks remain unchanged. This does not change the legacy live-monitor interlock.
Rollback reverts the CI and parity pins together while retaining any offline ledgers.

## Stage 20: archive historical paper fills from one PostgreSQL snapshot

An authorized migration caller can pass an attested Store, a dedicated Terminan
PaperReplayLedger and a stable source ID to archive_paper_fills. The function uses
one REPEATABLE READ READ ONLY transaction and two named cursors. The first scans
the digest and count, and the second transfers the canonical rows from that same
snapshot into Terminan's existing atomic importer. The two scans use the existing
Meta digest-v1 encoding and bounded batches of 256 rows. Preserve the original
database backup, source ID and returned digest. A retry with a changed snapshot
must refuse under the existing source ID. Verify with Terminan restore_meta_fills.
No historical rows are modified in Meta. Settings and level_map are outside this
paper-fill contract, and the live interlock remains in place.

Qualification pins Terminan #91 0f3b1408ada9a2cdea20e66ec56840d5bb196bac and Math
#122 876b31f2310827d417e70ed22d0e9b5cfc9b5320. To roll back, revert the source
commit while retaining the PostgreSQL backup and any committed Terminan archive.
