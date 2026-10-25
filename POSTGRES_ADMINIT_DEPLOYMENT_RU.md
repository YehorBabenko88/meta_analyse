# PostgreSQL ADMINIT — G0/G1 и план развёртывания

Дата: 2026-10-25. **ADMINIT NO-GO.** Разработка и offline-тесты не разрешают создание физического кластера.

## Исходные границы

Существующий PostgreSQL 18.1 на порту **5432** не изменять и не использовать как тестовую БД. Новый кластер — только после отдельного G1, на `127.0.0.1:55480`, без Windows service, под `%LOCALAPPDATA%\MetaAnalyseCommissioning\<новый-идентификатор>\pgdata`. Выделенная база/LOGIN `meta_commission_<session>`, не-superuser, без CREATEDB/CREATEROLE/REPLICATION. Никогда не использовать production DSN или credentials.

Код из `commissioning/prepare-private-cluster.ps1` и `commissioning/initialize-private-schema.py` уже реализует часть guard-контракта, но их запуск на ADMINIT запрещён до G1. Этот PR не запускает их.

## G0: только чтение, без подключения к БД

1. Зафиксировать точные commit SHA/tree и manifest. Проверить `git status --porcelain` (пусто), подписать разрешённый набор скриптов.
2. Сверить наличие PG18.1 binaries и их хеши с утверждённым manifest; не подменять PG18.6 hosted evidence.
3. Read-only OS inventory: `Get-Service *postgres*`; `Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 5432,55480`; `Get-CimInstance Win32_Service | Where-Object Name -match 'postgres'`. Запретить любые изменения по результатам инвентаризации.
4. Проверить, что предполагаемый каталог НЕ существует, находится под разрешённым корнем, все ancestors не reparse points, нет пересечения с действующим PGDATA, а 55480 свободен. Проверить права каталога и достаточный запас диска.
5. Зафиксировать владельца процессов/служб и существующий 5432 без попытки аутентификации. При конфликте — BLOCKED.
6. Проверить новое DPAPI CurrentUser enrollment, точную привязку source/host/user и согласование оператора. Без них G1 запрещён.

## G1: отдельно разрешаемая операция (НЕ выполнять сейчас)

После явного G1 оператор должен заново сверить все G0 predicates и использовать существующий `prepare-private-cluster.ps1` с параметрами `-ExpectedSha`, `-Manifest`, `-ManifestSha256`, `-Enrollment`, `-DataDirectory`, `-SessionName`, `-OperatorApproved` и `-PgBin`. Не хранить пароли в аргументах/файлах/логах. Никаких `DROP`, `pg_ctl stop` или `initdb` для неизвестного/существующего каталога. Затем отдельная аттестация точной идентичности кластера и только после неё — schema initialization.

## Attestation contract

Новый opt-in `pg_cluster_attestation.py` проверяет `current_database()`, `current_user`, `server_version_num=180001`, `inet_server_addr()=127.0.0.1`, `inet_server_port()=55480`, `pg_control_system().system_identifier`, отсутствие superuser/createdb/createrole/replication и наличие LOGIN. Отказ доступа к `pg_control_system()` — BLOCKED, не fallback на port/version. Политика должна получить утверждённый system_identifier из независимого G1 receipt, а не из произвольного DSN. Контекст `authorized_private_connection(connect, expected)` из `pg_authorized_connection.py` выдаёт то же соединение вызывающему коду только после успешной аттестации; новая выдача требует новой проверки. Сам по себе импорт guard не защищает старые callers. Только пути, явно использующие этот контекст либо commissioning Store с обязательным ExpectedCluster, покрываются этим контрактом. Обычный Store без opt-in сохраняет прежний контракт и не является разрешённым commissioning writer.

## Тесты и критерии

| Контроль | PASS | FAIL/BLOCKED |
|---|---|---|
| 5432 isolation | Никаких соединений и изменений | Любое обращение к 5432 — STOP |
| DSN/cluster | Все 7 атрибутов совпадают | Любой mismatch/permission denial — BLOCKED |
| Роли | Dedicated nonprivileged login; нет чужих grants | Superuser/createdb/replication — FAIL |
| Advisory locks | Сериализация одного venue/symbol, bounded timeout | Deadlock/unbounded wait — FAIL |
| Batch/checkpoint | Один transaction, точное восстановление | Частичный commit/checkpoint drift — FAIL |
| Shutdown | Drain до освобождения ownership | Detached writer — FAIL |
| Recovery | Restart не создаёт дубликаты | Loss/corruption/false imported — FAIL |
| Lifecycle | 10 × 67, mandatory JUnit identities | Неожиданные skips/duplicates — FAIL |

План дополнительных disposable-тестов: crash injection до COPY, во время COPY, до checkpoint, после commit; concurrent same/different symbol; cancel during rollback; disk-full; max_connections; lock timeout; reparse path; неверные system_identifier/role/port/version. Запрещены production DSN и физический ADMINIT.

## 30m / 2h / 24h — только будущая программа

- **30m:** после отдельного G1, baseline identity, disk/memory/connection budgets, controlled archive imports и остановка с rollback proof.
- **2h:** только после 30m PASS; concurrent imports, reconnect, crash/restart, checkpoint invariants и bounded recovery.
- **24h:** только после 2h PASS; длительные метрики WAL/диска, latency, connections, memory, lock waits, resource leak и fail-closed recovery.

Остановка при любом неизвестном cluster identity, подключении к 5432, превышении budget, расхождении checkpoint, незавершённом writer, неконтролируемом UNVERIFIED или privacy incident. Никакой автоматической эскалации этапов.

**Статус:** SOURCE IMPLEMENTED (opt-in guard) / SYNTHETIC FAKE TESTS PASS / DISPOSABLE PG NOT YET VERIFIED / G0 NOT EXECUTED / G1 BLOCKED / ADMINIT NO-GO.

## PlanOnly и rollback — уточнение

Новый `pg_cluster_plan.plan_only` — чистая функция без IO. Он отклоняет порт 5432, wildcard host, недопустимые роли и пересечения с явно переданными существующими PGDATA. **Это не физическая проверка существования каталога, symlink/junction, ACL, диска или слушателя.** Эти предикаты должны быть заново подтверждены G0 непосредственно перед отдельным G1; между проверкой порта и bind остаётся TOCTOU. Нельзя выдавать результат PlanOnly за разрешение initdb.

**Rollback после разрешённого G1:** сначала остановить только новый postmaster, причём после подтверждения PID, data_directory, system_identifier и владельца. При несовпадении — остановиться и не трогать процесс. Не использовать `DROP DATABASE`, `Remove-Item -Recurse` или `pg_ctl -D` для непроверенного каталога. Сохранять частично созданный новый PGDATA для ручного разбора; удаление требует отдельного разрешения. Не затрагивать 5432 и Windows services.

**Открытые блокеры:** независимое извлечение ожидаемого system_identifier в G1 receipt, read-only проверка роли/GRANTs и проверка `pg_control_system()` на disposable PG18.1. Код PlanOnly и аттестации не подключён к физическому setup; G1 по-прежнему запрещён.


## Интеграция 2026-10-25: происхождение и пределы доказательства

Выбраны только `pg_cluster_attestation.py`, `pg_cluster_plan.py`, их offline-тесты и этот документ из PR34 `f80469ebb174d402e56c91724c120324c8567bce`. Из PR45 `dfafc6159f4d7566611f37f5e29d58740b35da55` выбраны контекст соединения, отрицательные проверки канонического идентификатора/имени и соответствующие fake-тесты; ветка целиком и inherited CI не переносились.

Отрицательные red/green проверки выявили и закрыли: пустой session suffix, зарезервированную bootstrap роль, имена длиннее 63 ASCII байт, неканонические/выходящие за uint64 system_identifier, неоднозначные Windows-компоненты PGDATA (reserved device, завершающие точка/пробел), malformed результаты аттестации без стабильного refusal code. Исправлен также fake из PR45: transaction context отделён от connection context, чтобы проверять фактическое закрытие соединения один раз.

Эти проверки не доказывают physical ownership, отсутствие reparse points, существующие GRANTs, чистоту кластера или runtime совместимость с PostgreSQL. Аттестация требует отдельного `verify_database_role` для ownership/session/privilege predicates и независимого утверждённого G1 receipt. Ни system_identifier, ни разрешение на DDL/DML нельзя получать из того же произвольного соединения, которое предстоит проверить. Неизвестный receipt означает отказ до подключения.

Fake-тесты выполняют строки SQL только на Python-объектах; реальные SQL, кластеры, Windows inventory, сеть и G0/G1 не запускались. Ownership rollback остаётся процедурным контрактом выше: не реализована автоматическая остановка/очистка, и PlanOnly их не разрешает.
