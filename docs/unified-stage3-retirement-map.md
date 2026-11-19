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