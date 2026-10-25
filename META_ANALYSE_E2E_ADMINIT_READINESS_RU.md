# MetaAnalyse — готовность E2E на ADMINIT (25.10.2026)

**Роль:** независимый System Architecture / Integration QA. **Решение: ADMINIT NO-GO.**
Аудит по исходному коду и CI; реальные публичные потоки Bybit, физический ADMINIT, торговые аккаунты и production PostgreSQL не использовались.

## 1. Контрольные версии и доказательства

| Объект | Точный SHA / evidence | Ограничение |
|---|---|---|
| Commissioning-кандидат PR #12 | `86181d2d110688c13250a8be26b8743bcd1eb8e9` | CI [39490043666](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39490043666) и [39490043670](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39490043670) SUCCESS; физическая проверка отсутствует |
| Order Flow PR #7 | `0086e338ee668f2fb1b4a9dd7253b16b8469ce13` | Автоматическое восстановление присутствует в коде; [39444166085](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39444166085) SUCCESS, но нет независимой физической приёмки |
| Integration CI PR #9 | `aa43bf08672e571aedc3cdd60e47488b39f3ec25` | [40183282404](https://github.com/YehorBabenko88/meta_analyse/actions/runs/40183282404) FAILURE; Windows PG18 environment блокер |
| Общая ветка PR #10 | `38cf43ec781be9c4d7ebb98fb97525b3686a3c40` | Не равна актуальному PR #12 |
| Privacy/evidence PR #30 | `6d01bf3d9f4118ac336624c9986c4ed876edd445` | Шесть Actions QUEUED на момент проверки; отсутствие terminal PASS |

Нельзя смешивать результаты разных SHA и считать SKIPPED = PASS. G0 требует один immutable commit/tree с собственными тестами и артефактами.

## 2. Фактическая архитектурная карта

`Bybit REST (instruments, candles, OI, overview) / Bybit public WebSocket (trades, orderbook)`
→ `RawTradeStream / OrderBookStream / MarketCollector`
→ `ExecutionAggregator / OrderBook.apply / MarketHealthMonitor`
→ `RawPipeline / MarketStore / RawStore / PostgreSQL schema meta_analyse`
→ `DesktopService snapshots / AnalysisSession / PySide6 Window`.

Независимая ветка: `Archive transport → audit / receipt → archive_db_import → checkpoints → PostgreSQL → flow_history_storage → UI`.

| Компонент | Реализовано | Не доказано / экспериментально |
|---|---|---|
| REST и WebSocket | Подписка, reconnect, получение публичных данных, heartbeat transport | Длительная сетевая устойчивость, корректное обнаружение всех потерь |
| Orderbook | Snapshot/delta, проверка монотонности u/seq, INVALID, reconnect, per-symbol silence watchdog, immutable snapshot | Overflow и backpressure без ложного VALID; реальная полнота sequence |
| Trades | Приём исполнений, проверка и агрегация, уникальный ключ persistence | Exactly-once от биржи до UI при сетевых потерях |
| PostgreSQL | Схемы, записи, idempotent conflict handling, transaction contexts | Crash-at-commit/WAL и 24-часовой рост/retention |
| Archive | Аудит/receipt, импорт, checkpoint и resume | Совместная проверка всех отказов между receipt, commit и checkpoint |
| Desktop | Worker loop, queued Qt signals, read-only/paper UI, status UNVERIFIED | UI freshness при молчании сети и большой истории; физический p95 |
| Health | Event/gap counters, ages, invalidation | Полное обнаружение silent loss и мониторинг очередей/ресурсов |
| Shutdown | Закрытие producer перед client, drain фоновых DB потоков | Завершение бесконечно заблокированного SQL; forced-kill recovery |
| Commissioning | Документация, synthetic tests, CI artifacts | G0/G1 на ADMINIT и полевые логи 30m/2h/24h |

## 3. Producer → consumer → контракт → тест → риск

| Producer → consumer | Обязательный контракт | Доказательства | Риск |
|---|---|---|---|
| Bybit WS → OrderBookStream | Нет VALID без fresh snapshot в текущем connection epoch | `tests/test_orderbook_recovery.py`, `tests/test_orderbook_autonomous_recovery.py` | P0: slow-consumer overflow не доказан |
| OrderBookStream → MarketCollector | Immutable book, timestamp UTC/ms, invalidation прежде публикации | PR #7 tests | P1: исключение consumer и повторный reconnect |
| RawTradeStream → RawPipeline | Сохранение до аналитической публикации; dedup по (symbol,execution_id) | RawPipeline/RawStore unit/integration | P0: неполная история при silent loss |
| RawPipeline → PostgreSQL | Transaction commit либо rollback, отмена не бросает активный to_thread | `tests/test_integration_contract_shutdown.py` | P1: принудительное завершение и неограниченный I/O |
| Archive → receipt → DB | Привязка bytes/hash/source, checkpoint атомарен с batch | archive/storage integration | P1: crash matrix не исчерпана |
| PostgreSQL → flow history → Qt | UTC [start,end), Decimal, truncated = UNVERIFIED | flow history tests | P1: large history/pagination |
| Worker → Qt | Queued immutable DTO, no blocking I/O на UI | lifecycle, flow stress | P1: stale status и p95 под нагрузкой |
| CI → G0 | Exact SHA/tree, тестовый inventory, no unexpected skip, artifacts, dependency lock | PR #9/#12 Actions | P1: evidence provenance между PR |

## 4. Дефекты и блокеры

**P0-01: недоказанная непрерывность orderbook при перегрузке.** `src/meta_analyse/orderbook_stream.py:OrderBookStream.run` задаёт `max_queue=1024`, но лимит сам по себе не обнаруживает loss. Synthetic: 10 символов, producer быстрее consumer, принудительный drop/overflow, затем корректная delta; FAIL при публикации VALID без нового snapshot.

**P0-02: нет физически подтверждённого сквозного G0.** Нужен один exact-SHA candidate с реальными публичными данными, disposable PostgreSQL и локальным read-only UI; никакого live order routing.

**P1-01: неопределённый верхний предел завершения SQL.** `pipeline.py`, `market_collector.py`, `desktop.py:closeEvent`; ожидание worker не равнозначно принудительной отмене синхронной транзакции. Synthetic: удерживать DB transaction >10 секунд; UI показывает incomplete, worker и ресурсы не освобождены, нет ложного SUCCESS.

**P1-02: UI stale data.** `desktop_service.py` / `desktop.py`: проверять age и статус на каждом обновлении, при потере feed скрывать актуальные торговые метрики и помечать UNVERIFIED.

**P1-03: Windows PG18 CI.** PR #9 на `aa43bf0` не подтверждён зелёным; нельзя fallback на PG17. Нужна воспроизводимая установка PG18 на disposable hosted runner и version assertion.

**P1-04: Evidence provenance.** Каждый release пакет должен связывать SHA/tree, workflow run+attempt, JUnit test identities, skips, artifacts SHA256 и redaction result.

**P2-01: документация и лимиты.** Явно описать reconnect/backoff, DB growth, retention, admission, UI history pagination, эксплуатационные настройки и ограничения.

## 5. Минимальная матрица E2E-тестов

| Тест | PASS | FAIL/BLOCKED |
|---|---|---|
| Snapshot → delta → persisted UI | Совпадают символ, epoch, u/seq, timestamp, DB row, UI quality | Несогласованность или отсутствие evidence |
| Invalid delta → reconnect → snapshot | Немедленно INVALID, новый epoch, только fresh snapshot восстанавливает VALID | Любая delta восстанавливает VALID |
| Duplicate/out-of-order | Нет двойной записи/ложного VALID | Повторные данные приняты как новые |
| Silent socket / silent symbol | Watchdog сбрасывает состояние, reconnect в заданном тайм-ауте | Stale отображается как актуальное |
| Queue overflow / slow consumer | Ограниченная память; потеря обнаружена или поток fail-closed | Молчаливая потеря при VALID |
| PostgreSQL outage/rollback | Нет ложного persisted, checkpoint не продвинут | Успех до commit |
| Shutdown during write | Не подтверждается остановка до завершения commit/rollback | Ресурсы закрыты при активной записи |
| Archive re-import | Idempotent rows, receipt/hash совпадают | Дубликаты или смешанные source |
| Restart/crash | Состояние UNVERIFIED до resync, checkpoint согласован | Старый VALID переживает restart |
| UI 20 symbols | Без блокировки event loop, p95 измерен, freshness видим | GUI freeze / stale status |

## 6. Этапы испытаний ADMINIT — только после отдельного допуска

**G0 (offline):** exact SHA/tree; все обязательные Windows/Linux PG18 CI успешны, ноль неожиданных skips; fault-injection P0; JUnit/artifact hashes; configuration redacted; подтверждённый no-order routing. Любое отсутствие = BLOCKED.

**G1 (короткий контролируемый запуск):** отдельное явное разрешение, публичные read-only endpoints, изолированная БД, оператор и rollback. Никаких ордеров.

| Длительность | PASS | FAIL / BLOCKED | Evidence |
|---|---|---|---|
| 30 минут | 100% подписанных символов получили fresh snapshot; 0 false VALID; 0 unexplained DB gaps; UI p95 < 100 ms; shutdown без активных writes | Любая ложная достоверность, потеря записи, неизвестный SHA | Timestamped WS epochs, DB counts, GUI latency, logs |
| 2 часа | 0 необъяснимых queue drops; RSS рост < 20% после warmup; reconnect тесты восстанавливают VALID только после snapshot; 0 orphan writes | Невосстановленный feed, unbounded queue/RSS, stuck shutdown | RSS/queue depth series, reconnect ledger, DB/WAL stats |
| 24 часа | 0 false VALID; 0 data-integrity mismatches; диск не заполнен; restart/retention проверены; clean shutdown | Disk pressure без fail-closed, memory leak, missing evidence | Resource metrics, disk usage, retention receipts, restart logs |

Численные пороги — **предварительные критерии проекта**, а не подтверждённые показатели приложения. G1, 30m, 2h и 24h требуют отдельных решений о допуске.

## 7. Предлагаемые Draft PR

1. **Order Flow owner:** packet-drop/overflow fault harness и state-machine invariants, без реальных аккаунтов.
2. **Storage owner:** PostgreSQL18 disposable crash-at-commit/rollback/lock witness.
3. **Integration CI owner:** Windows PG18 installation + exact SHA/JUnit/artifact provenance.
4. **Desktop owner:** stale-data UI gate и bounded rendering under load.
5. **Commissioning owner:** G0 evidence pack, конфигурация и operator checklist.

## 8. Итог

**ADMINIT — NO-GO.** Offline code и CI могут продолжаться. До G0/G1 запрещено трактовать успешные unit tests как разрешение на физический 30m/2h/24h прогон. Merge, deployment и торговые операции не выполнялись.
