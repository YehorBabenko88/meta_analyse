# MetaAnalyse ADMINIT E2E — финальная независимая оценка (25.10.2026)

**Решение: G0 NO-GO / G1 BLOCKED.** Аудит не включает запуск ADMINIT, реальный public Bybit, торговые ключи, SQL-модификации или длительные испытания.

## Точный источник

База этой ветки — PR #35 SHA `e4bc8bd6a1faa7103244423bd0b00948bad8dba2`, основанный на PR #12 SHA `86181d2d110688c13250a8be26b8743bcd1eb8e9`. PR #35 CI на исходном SHA: runs [40200166949](https://github.com/YehorBabenko88/meta_analyse/actions/runs/40200166949) и [40200166782](https://github.com/YehorBabenko88/meta_analyse/actions/runs/40200166782) были QUEUED при первичной проверке; не считать PASS без terminal результатов. Точный HEAD исправлений фиксируется GitHub PR.

## Архитектура и source review

| Producer → consumer | Контракт | Реализация / риск |
|---|---|---|
| Bybit public REST → runtime/overview | Валидированные инструменты, timestamps, bounded HTTP | Реализовано частично; отсутствие физической TLS/network проверки |
| Bybit public WS → OrderBookStream → OrderBook | Fresh snapshot после invalid delta, u/seq строго возрастают, reconnect | Реализовано; seq gaps, которые не проявляются как регрессия, нельзя доказуемо обнаружить только по monotonic |
| OrderBookStream → MarketCollector → MarketStore | Immutable BookSnapshot, запись до callbacks | Есть; `max_queue=1024` — transport buffer, а не проверка всех drops |
| RawTradeStream → RawPipeline → RawStore | Idempotent (symbol, execution_id), commit прежде analytics | Есть; exactly-once от биржи до диска не гарантируется |
| Archive → receipt → archive_db_import → checkpoints | Верификация исходных байтов, атомарность batch | Реализовано, forced-kill checkpoint matrix не подтверждена |
| PostgreSQL → flow_history_storage → DesktopService → Qt | UTC, Decimal, immutable DTO, UNVERIFIED при неполной истории | Есть; bounded rendering, UI freshness на реальном рынке не доказаны |
| AnalysisSession → worker shutdown → DB | drain `to_thread`, не закрывать активную запись | Есть; stuck DB I/O и crash-restart требуют физической проверки |

## P0 / P1 / P2

**P0-01:** transport-only probe ранее возвращал `PASS`, хотя не выполнял PostgreSQL и Qt. Исправлено на `TRANSPORT_PASS`; это не G0/G1 и не полный E2E.

**P0-02:** slow-consumer queue overflow не имеет подтверждённого production механизма, который гарантирует `INVALID` при loss. `tests/test_integration_contract_orderbook_pressure.py` моделирует требуемый контракт, но **не является интеграционным тестом реального WebSocket buffer**. Требуется instrumented bounded application queue, overflow counter и принудительный reconnect после overflow.

**P1-01:** в probe первый валидный callback после gap считается snapshot; текущий callback не передаёт kind/epoch. Нужны явные `snapshot_received` и epoch из transport, иначе невозможно независимое доказательство fresh snapshot.

**P1-02:** UI health helper — offline классификатор; фактическое Qt-представление и временные пороги должны быть проверены отдельным GUI harness.

**P1-03:** PostgreSQL crash-at-commit, rollback, locks, archive checkpoint recovery, retention и disk pressure требуют disposable PG18 witness.

**P1-04:** exact-SHA/JUnit/artifact provenance и Windows PG18 CI должны завершиться terminal PASS; SKIPPED не PASS.

**P2-01:** resource budgets не instrumented end-to-end. Нужны RSS/CPU, queue occupancy/drop counters, DB size/WAL, disk free, UI p95 и reconnect epochs с красным флагом при отсутствии метрики.

## Следующие тесты и допуски

| Этап | PASS | FAIL | BLOCKED |
|---|---|---|---|
| G0 offline | Exact SHA/tree, Windows/Linux PG18 CI, no unexpected skips, fault injection, zero false VERIFIED, reproducible artifacts | Любой false VALID, broken rollback, неверный SHA | Нет полного evidence |
| G1 short public | Read-only public Bybit + disposable DB + GUI, нет trading keys/orders | stale data CURRENT, loss без INVALID | G0 не пройден |
| 30m | Все символы получили fresh snapshot, 0 false VALID, 0 unexplained DB gaps, UI p95 <100ms | freeze, missing writes, false VERIFIED | Нет DB/UI witness |
| 2h | Bounded queue/RSS, reconnect только после snapshot, 0 orphan writes, shutdown завершён | silent drops, stuck worker, OOM | Нет queue/DB metrics |
| 24h | 0 integrity mismatches, disk/retention/restart подтверждены, resource trend stable | disk exhaustion, leak, false VERIFIED | Нет 24h evidence |

Порог p95 — проектное условие, не результат измерения. Отдельное разрешение требуется перед каждым этапом. Немедленный STOP: false VERIFIED, неизвестный SHA, потеря целостности SQL, неограниченная память/диск, попытка размещения ордера.

## Отдельные Draft PR для подтверждённых работ

- Order Flow: реальные slow-consumer/queue overflow tests + overflow→INVALID→reconnect→snapshot.
- Storage: PG18 crash/rollback/checkpoint witness.
- Desktop: stale Qt status и UI p95 с 20 инструментами.
- CI: provenance SHA/tree/run/attempt/artifact and skip inventory.

**ADMINIT остаётся NO-GO.** Никаких merge, deployment, физических испытаний и торговых операций.
