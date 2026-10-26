# ADMINIT PR60 — PostgreSQL G1 Safety Review

Дата: 2026-10-26. Проверенный HEAD: `0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30`. Исходный PR #60 не изменён.

## Проверенные источники

`pg_cluster_attestation.py`, `pg_authorized_connection.py`, `pg_checkpoint_witness.py`, `pg_cluster_plan.py`, `prepare-private-cluster.ps1`, `initialize-private-schema.py`. Предыдущие commissioning и storage guards проверены по исходникам; полная физическая проверка запрещена.

## Source review

- **Attestation:** строгое совпадение version_num 180001, IPv4 loopback 127.0.0.1, port 55480, database/user/owner, `system_identifier`, запрет superuser/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS, membership и CONNECT к другим БД. SQL использует `pg_catalog` и read-only transaction. Недоступный `pg_control_system()` приводит к отказу, а не к ослаблению.
- **Connection:** `validate_connection_parameters` запрещает унаследованные PG* переменные и неразрешённые параметры; `authorized_private_connection` не выдаёт соединение до аттестации. Общий `Store.connect` не защищён автоматически; каждый commissioning DDL/DML caller требует доказанного opt-in gate.
- **PlanOnly:** чистый расчёт, отказывает для 5432, wildcard, недопустимых PGDATA и пересечений из переданного списка. Не является реальной проверкой reparse points или замены каталога.
- **Provisioning:** `prepare-private-cluster.ps1` ограничивает хост/учётную запись, source/enrollment, новый PGDATA, SCRAM, порт 55480, бинарную версию 18.1. После `initdb` получает system_identifier через `pg_controldata` до старта сервера. Но это не формирует отдельно утверждённый immutable receipt для следующего процесса.
- **Schema:** `initialize-private-schema.py` валидирует параметры и вызывает attestation до SCHEMA DDL, однако `--cluster-system-identifier` поступает из CLI и не сверяется с отдельным независимым G1 receipt. Trusted startup options ограничивают statement/lock timeout, но фактический server-side контракт нуждается в disposable PG18.1.
- **Checkpoint witness:** read-only WAL/checkpoint observation; `OBSERVED` не является физическим сертификатом crash durability. Не запускает CHECKPOINT.
- **Rollback:** при сбое provisioning оставляет новый каталог/процесс для проверки ownership; автоматическое удаление и остановка неизвестного PID отсутствуют. Для физического rollback требуются точные PGDATA, system_identifier, owner, PID/start time, binary и повторная проверка перед действием.
- **TOCTOU:** проверка порта завершается до bind; проверка reparse ancestors и существования PGDATA не удерживает handle до `initdb`. Замена пути между проверкой и созданием остаётся риском.

## Exact hosted evidence

PR #60 HEAD `0cc8c44d...`: CI run 40399605883 SUCCESS (Windows, Linux, archive); ADMINIT final integration synthetic 40399605857 SUCCESS; Kernel offline 40399605833 SUCCESS; Native SCM synthetic 40399605937 SUCCESS; Public JUnit privacy synthetic 40399605895 SUCCESS. В этом аудите не загружены и не сверены все raw JUnit/ZIP/attempt/job manifests. Не выдавать synthetic PASS за физический G1.

## P0 / P1 / P2

**P0:** G0 FAIL_CLOSED, G1 не разрешён; нет отдельно утверждённого и проверяемого system_identifier receipt, привязанного к PGDATA/owner/source и schema initializer. Нет доказанной физической изоляции существующего 5432.

**P1:** Windows PGDATA reparse/path replacement и порт TOCTOU; реальная PG18.1 catalog privilege matrix с dedicated non-superuser; полная карта commissioning Store/Window callers; rollback ownership и crash/cancel/disk-full recovery.

**P2:** resource budgets, long-running WAL/checkpoint/orderbook recovery, 30m/2h/24h испытания после отдельного допуска.

## Disposable PG18.1 acceptance (не выполнять на ADMINIT)

1. Новый ephemeral PG18.1 с отдельно записанным до соединения `pg_controldata` system_identifier; read-only SQL attestation должна совпасть.
2. Отдельная роль/БД без дополнительных memberships; проверить реальные права `pg_control_system()` и `pg_control_checkpoint()`. Отказ — BLOCKED, не выдавать broad GRANT автоматически.
3. Неверные system_identifier, port=5432, host, database, role, server_version_num, grants, PG* env, search_path: отказ до DDL/DML.
4. Atomic COPY/batch+checkpoint, два конкурентных импорта, lock timeout, rollback и повторный импорт без дублей.
5. Fault injection до COPY, до checkpoint, после commit, restart и disk-full; сверка WAL/rows/checkpoint.
6. Repeated cancellation и shutdown drain: никакого detached writer, все транзакции завершены до закрытия соединений.
7. Windows disposable path replacement/junction и безопасный rollback только по доказанному ownership.
8. JUnit identities, exact SHA/tree/run/attempt/job, privacy-projected artifacts; отсутствие unexpected skips.

## G1 stop conditions

Любое обращение к существующему 5432; неизвестный/сменившийся PGDATA, PID, owner, system_identifier или порт; ошибочные privileges/DSN; неаттестованная DDL/DML; partial checkpoint, orphan writer, uncontrolled disk/WAL growth, privacy leak — немедленно STOP/NO-GO. Не запускать `pg_ctl`, DROP или recursive delete на неизвестном ресурсе.

## GO/NO-GO

| Gate | Статус |
|---|---|
| Exact-source hosted CI | PASS |
| PostgreSQL source guards | PARTIAL PASS |
| Independent approved system_identifier receipt | BLOCKED |
| Real disposable PG18.1 SQL/permissions | NOT VERIFIED on PR60 in this audit |
| Crash/rollback/path replacement | BLOCKED |
| Physical G0 | FAIL_CLOSED |
| Physical G1 | **NO-GO** |

Никаких физических подключений, создания кластера, merge или deployment не выполнялось.
