# PostgreSQL ADMINIT G1 — независимая приёмка

Дата: 2026-10-25. База PR #34: `f80469ebb174d402e56c91724c120324c8567bce`.

## Архитектура

Существующий PostgreSQL 18.1 на **5432** остаётся неприкосновенным. Проектируемый отдельный кластер: PostgreSQL 18.1, `127.0.0.1:55480`, новый каталог под `%LOCALAPPDATA%\MetaAnalyseCommissioning`, отдельные `meta_commission_*` database/role, SCRAM, без Windows service, superuser, CREATEDB, CREATEROLE, REPLICATION для session role.

G0 — независимая read-only инвентаризация путей, служб, слушателей, процессов, ACL, reparse ancestors и диска. G1 — отдельное разрешение оператора после G0 PASS; в этой ветке G0/G1 не выполнялись.

## Исправления и ограничения

- `pg_cluster_attestation.py`: строгая проверка system_identifier, PostgreSQL version 180001, current_database, current_user, localhost binding, port 55480 и отсутствия опасных role flags. Unicode digits и неканонические имена ожидаемых ролей отклоняются.
- `pg_cluster_plan.py`: PlanOnly без IO; отказывает для 5432, wildcard адресов и явно переданных пересечений PGDATA. Реальная проверка junction/symlink/ACL/TOCTOU остаётся G0/G1 gate.
- `pg_authorized_connection.py`: opt-in wrapper, который предоставляет соединение вызывающему коду только после успешной read-only аттестации. Не заменяет уже существующие вызовы `Store.connect` или commissioning schema initializer; их полная интеграция ещё не доказана.
- Существующие `prepare-private-cluster.ps1` и `initialize-private-schema.py` сохраняют source/enrollment guards. Перед физическим использованием требуется отдельно доказать fail-closed ownership rollback, проверку system_identifier по независимому receipt и отсутствие races между проверкой каталога и initdb.
- Advisory locks, COPY и checkpoint используют уже существующий транзакционный импорт; новые crash/disk-full tests на disposable PG18.1 ещё не выполнялись.

## Rollback

Остановка только нового postmaster после подтверждения `system_identifier`, PID, owner, port и точного PGDATA. При несоответствии — отказ без воздействия. Не удалять неизвестные/частичные каталоги, не выполнять DROP для существующего кластера. Cleanup только по отдельному подтверждённому ownership receipt.

## Evidence matrix

| Контроль | Статус |
|---|---|
| Source review / PlanOnly | PARTIAL |
| Offline negative tests | ADDED, NOT YET RUN |
| Disposable PostgreSQL 18.1 | BLOCKED |
| G0 physical inventory | NOT RUN |
| G1 cluster creation | NOT AUTHORIZED |
| Shutdown drain / crash recovery | PARTIAL, NEED FAULT INJECTION |
| Full DDL/DML attestation coverage | BLOCKED |
| Existing 5432 unchanged | No physical access performed |
| ADMINIT | NO-GO |

## P0/P1/P2

- **P0:** неизвестный G0, нет разрешения G1, физическая identity/ownership не подтверждена.
- **P1:** подключить guard к разрешённым schema/import call sites, аттестовать независимый system_identifier и role grants, проверить PGDATA replacement и rollback ownership.
- **P1:** disposable crash, cancellation, lock timeout, disk-full и checkpoint consistency.
- **P2:** ресурсы, 30m/2h/24h после отдельного допуска, без автоматического перехода.

**NO-GO.** Никаких подключений к ADMINIT, 5432, создания кластера, merge, deployment или smoke30.
