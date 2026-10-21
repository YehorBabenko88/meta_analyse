# Engineering audit — data provenance

## Confirmed
- GitHub Actions green on b6fa0d5 prior to this batch.
- Source of raw trades: Bybit V5 publicTrade, not MetaScalp aggregated tape.
- RawStore stores original exchange execution ID, timestamp, price, quantity and taker side.
- DB uniqueness by (symbol,execution_id) makes retries idempotent.
- Gap and out-of-order signals are explicit; no interpolation.

## Known limitations / must-fix before 24/7 production
- New RawStore and ExecutionAggregator are not yet wired into desktop runtime. The older MetaScalp aggregate collector is still active.
- In-memory deduplication grows unbounded in ExecutionAggregator. RawStore DB key is the persistent safeguard.
- Exchange websocket cannot guarantee replay of missed executions after disconnect; mark POC invalid until verified coverage.
- Even with uninterrupted connection, first/last partial minute cannot be declared complete without explicit session boundary policy.
- Per-symbol tick size must come from Bybit instruments-info; never apply a shared tick to all markets.
- Clock skew, batch reordering and Bybit trading pauses need audit.
- PostgreSQL schema migrations, storage quotas, retention and backup must be explicitly configured; never delete raw data without consent.
- Historical candle coverage is not yet verified against exchange listing time, delisting, trading pauses or API earliest available time.
- The desktop must not launch live order placement. Paper results require execution quality gate.
- User-created MetaScalp levels must never be deleted by the reconciler.

## Release gate
Do not merge until raw execution pipeline is integrated, persisted, monitored and tested against real exchange samples; historical scanner and MetaScalp level lifecycle are end-to-end tested on Windows.
