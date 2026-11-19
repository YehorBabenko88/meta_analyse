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
- Math Draft PR #121 pinned HEAD `c637500f857b95b2db731eb05dcdf26f52c7a06f`, verified source blob `python/market_profile_math.py` = `430ee36dfe0f71872e4f2ed35d4eaac918989fa4`.
- Exact same-input source parity check: `scripts/check_math_consumer_parity.py` loads only that verified Math blob; `.github/workflows/ci.yml` executes the check on Windows and Linux, independently of existing mandatory suites. This test is offline source parity, not real data, not a runtime Math import or end-to-end release proof.
- Concrete Meta call graph: `core.py:Minute.add -> price_bucket`; `core.py:Minute.poc -> volume_profile_poc(profile, close=minute.close)`; `footprint.py:Footprint.add -> price_bucket`; `footprint.py:Footprint.poc -> volume_profile_poc({price: cell.buy+cell.sell})`; `footprint.py:FootprintCell.delta -> executed_volume_delta(buy,sell)`; `footprint.py:Footprint.delta` sums those deltas. `core.py:PaperEngine.on_closed_minute` consumes Minute.poc, and belongs in Terminan later.
- **Do not switch these runtime imports yet**: Math #121 is a raw `python/market_profile_math.py` file without a verified, installable distribution/API and versioned Gateway contract. Math refuses zero/nonfinite prices that legacy Meta may accept; no full real-input-domain parity or rollback evidence yet. #114 must establish installer/import path first.
- Terminan #87 `66db839eff32bc6db135eac9e978a185de4feab5` and #88 `66217c11f6fb046deba91d10dacaf1871e8b6ee7` now reportedly share one `terminan/contracts.py` registry blob, but their tests, docs, full trees and PR ancestry differ. Meta must not assume combined runtime/merge acceptance; only an owner-approved single PR with cross-branch tests and import graph #114 can unblock strategy consumer migration.
- Current PR #81 is documentation/tests plus internal SQL dedup; it neither deploys a second market service nor changes user history.


## Stage 5: hard single-owner boundaries and executable launch fence

- **Bybit/Grid only.** Legacy Meta entrypoints still reach exchange: `desktop_service.py:DesktopService.initialize` creates `exchange.BybitPublic`; `DesktopService._start_flow` calls `instruments(self.exchange)` and `AnalysisSession.start`; `collector.py:CollectorService.run` owns another BybitPublic/RawPipeline; `market_collector.py:MarketCollector.start` runs orderbook and OI collection; `raw_trades.py:RawTradeStream.run` contains direct Bybit WS. These are KEEP ONLY FOR TEST EVIDENCE until consumers switch to Grid APIs; they are **not** approved production connections.
- **One Terminan.** `desktop.py:main` now explicitly refuses obsolete Meta CLI start *before* QApplication/Window construction (test: `tests/test_desktop_flow_contract.py:test_legacy_desktop_cli_refuses_before_qt_or_exchange_start`). A direct `Window()` construction still exists for legacy isolated regression tests. This fence alone cannot disable previously deployed copies; Unified must control installation and service registration.
- **One PostgreSQL infrastructure owner (Unified).** Meta `commissioning/prepare-private-cluster.ps1`, `pg_cluster_plan.py:plan_only`, `storage.py:Store.initialize`, `storage_migrations.py`, `archive_db_import.py`, and `market_store.py` retain old cluster/schema/write paths. Distinguish infrastructure provisioning (Unified-only) from Grid market-schema ownership/writes; paper strategy result persistence -> Terminan. Do not run Meta commissioning/DB migrations in unified release. No database/table deletion yet.
- **One control plane/Gateway (Unified).** `headless_service.py:main/PrivateServer/Handler` is a second local server candidate; `analysis_session.py:AnalysisSession.start/stop` and `runtime.py:Runtime.run` are independent lifecycle candidates. Their test and provenance code must be mapped to Unified/Grid/Terminan; no second general orchestrator may survive. No direct SSH/LAN/SCM mutation was performed by this PR.
- `install.ps1` and the `meta-analyse` console script remain legacy artifacts; they are NOT the unified installer and still need dependent workflow/consumer inventory. The `meta-analyse` runtime entrypoint now fails closed, but source retention and historical installer availability remain a retirement blocker.
- **Dependency order:** Grid v1 REST/WS/provenance read API with read-only roles -> Math versioned distribution/compute API -> Terminan paper/visual API -> Unified Gateway/installer/operator scopes -> #114 consumers/import graph -> #116 physical E2E/rollback -> #115 archive review. Test and maintain all old data and branches until signed off.
