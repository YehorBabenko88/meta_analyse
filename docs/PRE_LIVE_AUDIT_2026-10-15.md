# Pre-live architecture audit — 2026-10-15

**Decision: NO-GO for live deployment or trade-entry decisions.** GitHub CI green is not an integration certification. This audit is static, based on the feature-branch source. No real Bybit, MetaScalp, or PostgreSQL integration was exercised.

## Requirement-by-requirement assessment

| Requirement | Status | Evidence / blocking gap |
|---|---|---|
| Bybit USDT linear perpetual volatility ranking | Partial | `exchange.py:top_volatile` ranks absolute 24h price change with turnover filter; not realized volatility. |
| Listing age >= 30 days | Implemented, unverified in live environment | `collector.py` filters `launch_ms` before selecting 20. |
| 20 instruments / dynamic refresh | Partial | `CollectorService` rotates raw-trade subscriptions; desktop uses different `Runtime`. |
| Historical candles for every supported interval | Partial | `exchange.INTERVALS` only M1/H1/D1/W1/MO1; no complete Bybit interval coverage, no scheduler in UI. |
| Historical raw trades | Missing | WS stores only trades observed since connection; no exchange historical tick backfill. |
| Order book snapshot and incremental deltas | Missing | Old MetaScalp runtime subscribes to book but does not reconstruct or persist it. No Bybit orderbook pipeline. |
| Open interest and history | Missing | No OI API, persistence, timeframe aggregation, or gap validation. |
| Cluster/footprint analysis | Partial | `core.Minute` computes price volume and buy/sell totals; no bid/ask per-price footprint, imbalance, stacked imbalance, or complete-minute guarantee. |
| Large resting orders | Missing | `RollingFlow.wall_score` takes a supplied size; no L2 lifecycle tracking or liquidity baselines. |
| Spoofing defenses | Missing | No order-book snapshot/delta reconciliation, order lifetime, cancel-before-touch, fill evidence, or confidence model. L2 cannot identify trader intent. |
| Tape speed near levels | Missing | `RollingFlow.metrics` global windows only; no level proximity, execution bursts, quality-gated signal, or UI. |
| Untouched levels all intervals | Partial | `untouched_levels` exists; `verified_levels` only supports M1/H1/D1 and assumes requested window sufficient for untouched-since-listing. |
| MetaScalp level lifecycle | Partial | `LevelSync` can replace app-owned notes and remove crossed lines; lacks verified live SDK contract and full application integration. |
| PostgreSQL ↔ terminal recovery | Partial | `SyncJournal` and `DurableLevelSync` exist; not called by desktop startup. |
| Desktop instrument selection and tape analyzer | Missing | `desktop.py` uses legacy MetaScalp aggregated trade runtime; Order flow tab says planned milestone. |
| Network/restart reliability | Partial | Read retries and WS reconnects exist; write reconciliation and startup replay not wired into running UI. |
| Trade execution | Not intended | No exchange order submission should be introduced without separate authorization. |

## Critical defects and blockers

1. **Split architecture:** `desktop.py` instantiates `Runtime`, not `CollectorService` or `terminal_pipeline`. Latest raw-trade and level safety mechanisms are not part of the desktop workflow.
2. **POC never trusted:** `ExecutionAggregator` creates every minute with `complete=False` and never upgrades it. Thus no minute can satisfy the `on_closed` eligibility predicate. This is fail-closed but not functional.
3. **Continuity cannot be proven from publicTrade WS alone:** initial connect calls `gap`; quality becomes false and never returns true. Do not silently set it true: missing executions are possible even within a connected stream.
4. **Unbounded memory:** `ExecutionAggregator.seen` and `closed` grow indefinitely; pipeline iterates only newly appended items but never releases old entries.
5. **Unsafe level write assumptions:** `ports.py` uses `signal-levels` endpoints, potentially signal/alert objects rather than purely decorative chart lines. Validate MetaScalp SDK semantics before enabling automatic deletion. `owned_id` depends on assumed response keys.
6. **Crossing safety:** `CrossingService` receives a `contiguous` flag derived from the same unverified WS quality. The flag is not sufficient evidence of complete trade history. Gap or unknown coverage must block removal.
7. **History validation:** fixed interval checker does not validate duplicates, OHLC consistency, exact bar closure, or launch-date alignment. Monthly/weekly calendar handling is incomplete.
8. **No order book integrity:** snapshot + sequence continuity + reset-on-gap are prerequisites for reliable resting-liquidity metrics and spoofing heuristics.
9. **No OI ingestion:** OI cannot be reconstructed from trades or DOM; needs independent timestamped Bybit API collection.
10. **Cross-system atomicity impossible:** PostgreSQL and MetaScalp cannot share a single ACID transaction. Use desired-state journaling, idempotent reconciliation, read-back verification, and retry after restart; never claim atomic writes.

## Required implementation gates before real-world testing

A. Unit tests for age boundary, all interval mapping, book snapshot/delta ordering, trade duplicates/reordering, stale snapshots, and cancellation/re-addition.
B. Deterministic recorded-message replay (including WS disconnect, lost response, delayed/out-of-order events, PostgreSQL failure) and bounded-memory soak tests.
C. Offline fake MetaScalp REST integration tests covering partial deletion, duplicate add, user-created lines, unexpected SDK response schema and restart reconciliation.
D. Isolated PostgreSQL test schema, migration rollback plan, retry/backpressure metrics and retention policy.
E. End-to-end desktop integration test: selected eligible symbols → historical quality check → computed levels → terminal reconciliation → tape-speed UI.
F. Only then staged paper-only validation with real market data and **no automatic exchange orders**.

## Anti-spoofing analysis design

A visible wall is *not* proof of genuine liquidity or spoofing. Record orderbook snapshot and sequence-valid deltas with exchange/receive timestamps. Track price-level quantity increases, decreases, lifetime, proximity to best bid/ask, distance to traded price, reappearance, and subsequent aggressive executions. Separate executed depletion from cancellation only when exchange data permits inference; L2 aggregation generally cannot attribute an individual participant or prove intent. Produce a probabilistic *ephemeral-liquidity warning*, not a definitive spoofing accusation. Suppress alerts on gaps, crossed books, stale depth, or uncertain execution correlation.

Tape-speed signals should use actual trade timestamps, rolling 1/5/15-second windows, volume and notional per second, buy/sell imbalance, acceleration vs trailing baseline, distance to verified level in ticks, and data-quality flags. No trading recommendation should be issued when book or tape is stale.
