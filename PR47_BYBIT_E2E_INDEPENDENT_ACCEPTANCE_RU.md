# PR #47 — независимая приёмка Bybit / E2E (25.10.2026)

**Вердикт: ADMINIT NO-GO; G2–G5 BLOCKED.** Проверен точный PR #47 HEAD `59626930a911c0dde330f7760c78ccd99468a1f4`. Отдельная ветка аудита основана непосредственно на этом SHA. Tree SHA требуется независимо подтвердить через GitHub Git Trees; не подменять commit SHA tree SHA.

## Источники и CI

- PR #47 [integration](https://github.com/YehorBabenko88/meta_analyse/pull/47), exact HEAD `59626930a911c0dde330f7760c78ccd99468a1f4`.
- [ADMINIT final integration synthetic](https://github.com/YehorBabenko88/meta_analyse/actions/runs/40203574132): QUEUED на момент первичной проверки.
- Остальные workflows того же SHA: CI, storage integration, public JUnit privacy synthetic — SKIPPED, а не PASS.
- PR #35 HEAD `e4bc8bd6a1faa7103244423bd0b00948bad8dba2`; PR #46 HEAD `499f232001d12fbc4e56782e191c6dc3d7ddae15`. Эти ветки не являются доказательством нового PR #47.

## Архитектура и контрактные границы

| Producer → consumer | Реализация | Незакрытый риск |
|---|---|---|
| Bybit REST → overview/instruments | Публичный read-only HTTP клиент, нормализация DTO | TLS/timeout/rate-limit в реальной сети не подтверждены |
| Bybit WS → OrderBookStream | Snapshot/delta, u/seq monotonic, reconnect, silence watchdog, epoch | Depth50: монотонность не доказывает отсутствие всех gaps |
| OrderBookStream → MarketCollector | Immutable `BookSnapshot`, valid/sequence/message_type, bounded transport queue | Нет гарантированного detection каждой потери из переполненной transport queue |
| MarketCollector → MarketStore/PG | DB write завершён до telemetry и UI callback | Нет физического commit/rollback witness на ADMINIT |
| RawTradeStream → RawPipeline → RawStore | Dedup по symbol/execution_id, gap flags | Невозможна биржевая exactly-once гарантия при silent loss |
| Archive → receipt → import → checkpoints | Audit/receipt, batch transactions, resume | Forced crash-at-checkpoint не подтверждён |
| PostgreSQL → DesktopService → Qt | Read-only/paper UI, immutable DTO, queued signals | Нет полной интеграционной проверки SQL→Qt с реальными публичными событиями |
| Worker → shutdown | Cancellation drain для `to_thread` | Неограниченный DB I/O не может обещать bounded physical shutdown |

## Приоритеты

**P0-01: false E2E promotion.** `scripts/public_bybit_e2e_probe.py` правильно возвращает `TRANSPORT_PASS`, но это не `FULL_E2E_PASS`. Любой release gate, принимающий транспортный результат за полный E2E, должен FAIL_CLOSED.

**P0-02: loss detection.** `src/meta_analyse/orderbook_stream.py` задаёт `max_queue=1024`. Это лимит buffering, не проверка continuity. Slow consumer/forced queue overflow требует измерения queue depth, overflow count, invalidation и нового snapshot. Synthetic `tests/test_integration_contract_orderbook_pressure.py` доказывает модель, не реальный transport.

**P1-01: resource budgets.** `sample_resources()` в public probe измеряет только число threads/tasks, **не CPU/RSS/disk/queue depth/Qt latency**. Нельзя выдавать G2–G5 PASS при отсутствии этих метрик.

**P1-02: commit-before-telemetry.** Добавлены offline negative/positive tests в `tests/test_integration_contract_market_commit.py`: ошибка DB блокирует telemetry/publish; успешный commit предшествует им. Это не замена реальному PostgreSQL.

**P1-03: sequence continuity.** `OrderBook.apply` отклоняет duplicate/out-of-order, но допускает пропуски `u`/seq, поскольку Bybit может пропускать идентификаторы. Требуется документированный invariant конкретной подписки depth50, а не произвольное требование `+1`.

**P1-04: UI health.** `health_state()` классифицирует `UNVERIFIED/STALE/CURRENT` offline, но не доказывает Qt presentation. При gap UI обязан немедленно скрывать CURRENT, до нового snapshot.

**P2-01: evidence.** Отчёт обязан связывать exact commit/tree, workflow/run/attempt/job, JUnit identity/skip inventory, artifacts SHA256 и redaction. Не считать queued/skipped jobs успехом.

## RED / GREEN

| Проверка | Состояние |
|---|---|
| Изолированные OrderBook invalid→reconnect→snapshot тесты | GREEN по ранее проверенным веткам; не заменяет PR47 |
| Новый offline commit-before-telemetry contract | NEW, CI ещё не подтверждён |
| Реальный Bybit public transport | BLOCKED — G1/G2 не разрешены |
| Реальный PG18 + Qt E2E | BLOCKED |
| Depth50 packet-loss/queue overflow | RED: witness отсутствует |
| Physical 30m/2h/24h | BLOCKED |

## G2–G5 runbook (не выполнять без допусков)

| Gate | Preconditions | Resource budgets / PASS | FAIL и немедленный STOP | Evidence / rollback |
|---|---|---|---|---|
| G2 короткий smoke | G0/G1 PASS, exact SHA/tree, только публичные endpoints, disposable PG18 | 100% symbols fresh snapshot; 0 false VERIFIED; UI p95 <100 ms; 0 unexplained DB gaps | private endpoint, order attempt, stale CURRENT, SQL mismatch | Redacted WS epoch timeline, PG counts, Qt latency; stop producers, drain writes, stop disposable DB |
| G3 30m | G2 PASS и отдельный допуск | No missing required metrics; RSS/CPU/queue/disk baseline; zero false VALID | OOM trend, queue drop, invalid data shown CURRENT | 30m time-series, JUnit, hashes, operator sign-off; graceful shutdown |
| G4 2h | G3 PASS и отдельный допуск | Reconnect with fresh snapshot; bounded memory and queues; zero orphan writes | No resync, unbounded memory, stuck shutdown | 2h reconnect/health/DB witness, rollback plan |
| G5 24h | G4 PASS и отдельный допуск | Retention/restart, disk headroom, zero integrity mismatches, no leaks | disk pressure, lost checkpoints, false VERIFIED | 24h resource/retention report, crash/restart receipts, rollback |

Порог p95 <100ms — предварительное требование, не измеренный результат. CPU/RSS/queue/disk limits необходимо зафиксировать по ресурсам ADMINIT до G2. Отсутствующая метрика = BLOCKED.

## Следующие отдельные PR

1. Production overflow instrumentation: bounded app queue + fail-closed reconnect and metrics.
2. Real PostgreSQL18 disposable commit/rollback/checkpoint witness.
3. Qt freshness and UI latency measurement harness.
4. Provenance evidence with exact SHA/tree/run attempt/artifact digest.

**Никаких торговых ключей, private endpoints, ордеров, merge/deployment и физических запусков.**


## Дополнение: cancellation/slow-write witness

На отдельной ветке PR #50 добавлены два offline fault-injection сценария:
- блокировка синхронной DB операции удерживает публикацию telemetry и UI до освобождения;
- отмена ожидающей задачи не освобождает ответственность за ещё работающий `to_thread`, и после завершения SQL не публикует ложное подтверждение.

Это **не физический PostgreSQL rollback**: тест использует управляемый fake DB. Для G2 требуется disposable PostgreSQL 18, SQL commit/rollback receipts, JUnit с точным SHA и контроль того, что активная транзакция не пережила подтверждённый shutdown.
