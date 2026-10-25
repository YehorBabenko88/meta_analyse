# MetaAnalyse E2E readiness — independent integration QA addendum (2026-10-25)

**Verdict: ADMINIT NO-GO.** This is an offline code/CI audit; no live Bybit connection, physical machine, deployment or merge.

## Exact source boundaries

- PR #7 `0086e338ee668f2fb1b4a9dd7253b16b8469ce13`: orderbook autonomous reconnect and immutable snapshots.
- PR #9 `383458001a65224094c43a049e20f9c9cbcef50c` before this addendum: JUnit/CI guards and cancellation-drain tests.
- PR #10 `38cf43ec781be9c4d7ebb98fb97525b3686a3c40`: older combined checkout; not equivalent to PR #7 HEAD.
- PR #12 `86181d2d110688c13250a8be26b8743bcd1eb8e9`: commissioning evidence candidate. CI runs 39490043666 and 39490043670 succeeded; not a physical GO.
- PR #28 `15a9d25233cc2383f2f771c0536bb1b1eeaae20a`: content-security synthetic workflow succeeded, other workflows policy-skipped; skips are not successes.

## Producer → consumer contracts

| Producer | Consumer | Enforced invariant | Gap |
|---|---|---|---|
| Bybit orderbook WebSocket | OrderBook.apply | Snapshot required; invalid delta resets validity | Missing independent packet-loss/overflow detection and physical network replay |
| OrderBookStream | MarketCollector / Qt | Immutable BookSnapshot in PR #7; per-symbol stale watchdog | Backpressure under slow callbacks and long reconnect exhaustion not demonstrated |
| RawTradeStream | RawPipeline | Idempotent execution key in PostgreSQL | Exchange-wide exactly-once delivery is not guaranteed |
| RawPipeline / MarketCollector | PostgreSQL | Drain of executor writes before cancellation completes in later candidate | Forced process kill and WAL recovery need separate disposable DB evidence |
| Archive audit/receipt | archive_db_import | SHA/receipt and checkpoint-based resume | Cross-version migration and crash-at-checkpoint proof required |
| PostgreSQL history | Desktop / Order Flow | UTC scoped, UNVERIFIED history, truncated data blocked | UI limit/pagination and large live data remain unproven |
| Worker loop | Qt closeEvent | Worker exit precedes accepted close; incomplete shutdown shown | Unbounded background SQL operation may leave window waiting indefinitely |
| GitHub Actions | Release decision | JUnit test identity, skip and count checks | Provenance binding across exact checkout, jobs, artifacts and evidence is incomplete |

## Prioritized unresolved defects and evidence

**P0 — end-to-end readiness:** PR #10 is not the same exact source tree as later PR #7 recovery fixes. Rebuild an isolated candidate and independently prove INVALID → new connection epoch → fresh snapshot → VALID on that SHA. An isolated PR #7 green test is not sufficient.

**P0 — overflow/data integrity:** bounded WebSocket `max_queue` limits buffering but does not prove that a slow consumer or dropped transport frames are always detected. Inject overload while preserving exact expected update IDs; assert no false VALID and require fresh snapshot on any unprovable continuity.

**P1 — shutdown:** `asyncio.to_thread` cannot stop an active DB thread. Drain mechanisms mitigate cancellation but cannot promise completion of indefinitely blocked I/O. Assert explicit incomplete state, no success acknowledgement, and no resource release before worker exit. Use disposable PostgreSQL with fault-injected blocking writes.

**P1 — CI:** earlier PR #9 run 39444240225 had Windows failure in the Windows Qt/disposable PostgreSQL step while Linux and archive passed. Root cause was not established by the available logs; never call that exact run green. The new JUnit parser hardening must be checked on both OS.

**P2 — docs:** default-branch README is skeletal and not evidence of full commissioning readiness. Release checklist should pin SHA, dependency lock, test inventory, CI run/job/attempt IDs and artifacts.

## Physical commissioning gates (do not run until explicitly approved)

| Stage | Minimum measurable acceptance | Evidence |
|---|---|---|
| 30 minutes | All subscribed symbols receive fresh snapshot; zero false VALID; UI responsive; zero unexplained persistence gaps; clean shutdown | Source SHA, config redacted, event/epoch timeline, JUnit, DB row counts, p95 UI latency |
| 2 hours | Bounded memory/queues, repeated disconnect recovery, no orphan writes, consistent checkpoints | RSS/queue time series, reconnect ledger, DB/WAL stats, fault logs |
| 24 hours | No leak trend, controlled disk-pressure behaviour, restart recovery, no silent stale display, complete shutdown | Longitudinal metrics, disk/retention evidence, crash-restart receipts and operator sign-off |

**Release rule:** any missing evidence, unexpected skipped mandatory test, failed job, stale orderbook marked VALID, unbounded write after claimed shutdown, or mismatched exact SHA = **NO-GO**.

## Suggested separate Draft PRs

1. Orderbook queue-overflow and slow-consumer continuity fault harness (Order Flow owner).
2. Disposable PostgreSQL crash/rollback/lock and shutdown ownership proof (Storage owner).
3. Combined exact-SHA CI evidence manifest, JUnit source identity and artifact provenance (Integration CI owner).
4. UI stale-data and large-history pagination acceptance (Desktop owner).

No merge/deployment/live trading authorized by this document.
