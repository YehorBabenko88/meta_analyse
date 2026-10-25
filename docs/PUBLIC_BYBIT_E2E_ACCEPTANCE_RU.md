# Public Bybit E2E — G0/G1, health и ограничения

**Статус: G0 NO-GO, G1 BLOCKED.** Скрипт `scripts/public_bybit_e2e_probe.py` — opt-in, read-only, только публичный Bybit WebSocket. Он не открывает торговых соединений, не изменяет PostgreSQL и не запускает Desktop. Не запускать его на ADMINIT до независимого G0/G1.

## Offline-проверки (без сети)

`python -m pytest -q tests/test_public_bybit_e2e_probe.py tests/test_orderbook_autonomous_recovery.py`

Результат тестов не заменяет проверку реального transport или физического UI. Synthetic tests не имеют права устанавливать G1=PASS.

## После отдельного допуска G1 — только публичный поток

`python scripts/public_bybit_e2e_probe.py --enable-public-network --symbols BTCUSDT --minutes 30 --output evidence/public-30m.json`

Запуск намеренно не автоматизирован в CI; при `CI` скрипт отказывает. Выход JSON содержит verdict, число свежих snapshot, epochs, updates, gaps, stale/pending symbols и превышение event budget. Для 2h/24h используйте соответственно `--minutes 120` / `--minutes 1440` **только после допуска предыдущего этапа**.

## Ограничения доказательств

Это transport probe, а не полный E2E Bybit → PostgreSQL → Desktop: в нём отсутствуют SQL rows/checkpoints, UI frame times, queue depth/RSS и disk retention. До реализации этих наблюдений и отдельного интеграционного witness полные 30m/2h/24h acceptance имеют статус **BLOCKED**, даже если transport probe выдаёт PASS.

`max_queue=1024` ограничивает внутреннюю очередь websockets, но не доказывает обнаружение всех packet drops. Нужны отдельные bounded backpressure/slow-consumer fault tests с принудительным invalidation и fresh snapshot; недостоверные данные никогда не должны получать VERIFIED.

## Предварительные критерии

| Этап | PASS только при | FAIL | BLOCKED |
|---|---|---|---|
| G0 | Exact SHA/tree, PG18 Windows/Linux CI, negative fault tests, no unexpected skips, zero live orders | false VALID, broken rollback, неверный SHA | Нет JUnit/provenance или CI terminal |
| 30m | Все подписанные символы получили fresh snapshot; 0 false VALID; UI p95 <100ms; 0 unexplained DB gaps | stale VALID, freeze, missing writes | Нет DB/UI evidence |
| 2h | Нет unbounded RSS/queues; reconnect после инъекции с fresh snapshot; 0 orphan writes | silent drops, OOM, stuck shutdown | Нет queue/RSS/DB evidence |
| 24h | Нет необъяснимых integrity mismatches; disk/retention/restart проверены | disk exhaustion без fail-closed, false VALID | Нет resource/retention evidence |

Порог UI p95 <100ms — проектный критерий, не измеренный результат. Порог памяти и размера БД следует зафиксировать перед G1 исходя из выделенного тестового ресурса.

## UI health — обязательный контракт

UI должен показывать `UNVERIFIED` после gap/reconnect, показывать `STALE` при превышении порога свежести, публиковать только immutable DTO из worker и не объявлять успешный shutdown до завершения SQL worker. Проверка выполняется в отдельном UI fault harness, не подменяется transport-only PASS.
