# ADMINIT: устранение G0-блокера и план допуска G1–G5

25.10.2026. Это план контролируемого тестирования, **не разрешение на установку**. Физический G0 остановлен после отказа execution policy Windows PowerShell. Не менять политику, не использовать Bypass, не переключать shell ради обхода запрета. Требуется согласованный с владельцем машины допустимый подписанный путь выполнения. Никаких действий G1 до полного G0 PASS и отдельного допуска.

## Источники

Интеграция начинается с PR32 `14025716972c9e9150f8af54bb7794e400993ed2`, tree `022c5b25e0ea830ee8fd467fefddadff016e19a5`; его ancestor PR30 `6d01bf3d9f4118ac336624c9986c4ed876edd445`. Три изменения PR31 (`449856c`, `0618024`, `da0fb4735d2019e0ffa8b9f796b73725272daa5f`) перенесены отдельно. Исходные ветки не переписываются. Exact final source/tree и CI фиксируются внешним отчётом после коммита, а не историческими receipts.

## G0: обязательный read-only checklist

Компактный `commissioning/adminit-g0-readonly.ps1` — только частичная инвентаризация: source/tree/clean, elevation, services/listeners, MetaScalp process count. Его `OBSERVATION_ONLY`, exit0 и `Authorization=NONE` **не являются G0 PASS**. Ошибка discovery приводит к BLOCKED, а не к утверждению о свободном порте. Скрипт не запускает hardened native collector.

После устранения policy-блокера владелец должен отдельно подтвердить все пункты:

| Проверка | Условие PASS | Стоп / evidence |
|---|---|---|
| Windows identity и elevation | Подтверждён intended test host/account; права достаточны для конкретных read-only запросов | Label компьютера сам по себе не attestation; SID/identity только приватно |
| Source | Отдельный exact final checkout, ожидаемые HEAD/tree, clean включая untracked | Любое расхождение BLOCKED |
| Python/PowerShell | Python3.12 из конкретного executable, venv в G1; допустимая PowerShell среда | Не ставить Python/не менять execution policy в G0 |
| PG services/ports | Успешные запросы, сохранённые приватно, existing5432 отдельно зафиксирован | Ошибка запроса = UNKNOWN/BLOCKED; не подключаться к неизвестному cluster |
| MetaScalp | Process identity и loopback API ownership проверены разрешённым способом; GET `/ping` без POST/DELETE | Process count не является identity/health; PPL/VM_READ/native identity остаются отдельными gates |
| Grid footprints | Владелец проверил известные каталоги/process footprints и отсутствие конфликта | Не перечислять/читать произвольные пользовательские файлы, не изменять Grid |
| TLS/network | Успешный public Bybit TLS с обычной проверкой сертификата | Никаких trading keys; не отключать TLS; REST success не означает WS continuity |
| Каталоги/ресурсы | Выбран новый owned test root, родитель доступен; filesystem permissions наблюдены без изменений; согласованы quota/floors | Read-only не доказывает возможность записи: проверка создания только G1 |
| Restore | План остановки, backups владельца, cleanup ownership, отсутствие автоматического перехода | Не трогать существующие данные ради проверки |

Предлагаемые defaults для обсуждения допуска: один инструмент BTCUSDT, один процесс приложения, PG loopback port55480 при подтверждённой свободе, очередь с жёстким лимитом, disk free floor10GiB, available RAM floor2GiB. Это проектные defaults, не фактические измерения ADMINIT и не автоматическое разрешение. Данные CPU/RAM/disk/TLS/API пока NOT_MEASURED из-за G0 stop.

## G1: только после отдельного допуска

Сначала plan-only manifest: final SHA/tree, абсолютные application/venv/log/data roots, собственник, выбранный порт, quota/retention, перечень допустимых файлов и rollback. Все каталоги новые; существующий путь/alias/reparse/collision даёт отказ. Не использовать общий `%LOCALAPPDATA%/MetaAnalyse` по умолчанию. Существующий `install.ps1` имеет winget fallback и editable installation; его нельзя запускать на ADMINIT без отдельного review и явных `-Python/-InstallRoot` в изолированном root.

Pinned lock уже существует, но hashes/wheel custody и воспроизводимый offline wheelhouse для физической установки ещё требуют подготовки и проверки. Новое окружение только Python3.12; `pip check`, configuration validation без secret echo, source receipt до/после установки. Не устанавливать службу/autostart, не менять PATH системы, firewall/AV/ACL.

PG18: отдельные owned binary/data/log roots; существующий5432 не изменять и не использовать. Новый порт — loopback only, не service. Сначала новый cluster, затем private attestation: server_version_num, data_directory/port/listen_addresses, `pg_control_system().system_identifier`, идентичность socket/процесса и ownership. При bootstrap исключить сетевой trust и публичное прослушивание; bootstrap superuser только для provisioning. После отдельного подтверждения attestation — выделенные database/schema и least-privilege runtime role, тест недопустимого DSN до DDL/DML, transactional migration, checkpoint/read-back, отказ на mismatch. DSN и passwords не в CLI/log/PR.

Cleanup только для собственных manifest-recorded путей и подтверждённого system_identifier. Если ownership/identity недоказаны, никакого DROP/recursive cleanup/stop по одному имени или порту. Existing5432 и пользовательские данные никогда не cleanup targets. Не заявлять cluster attestation до реального выполнения.

## G2–G5: отдельный допуск на каждый этап

| Этап | Проверки / метрики | Stop conditions / rollback |
|---|---|---|
| G2 functional | UI и collector только в isolated roots; public REST/WS; snapshot/delta/trades; sequence reset/gap/reconnect; bounded queue/backpressure; PG commit/checkpoint/read-back; UI thread heartbeat; controlled shutdown | Любой wrong source/DSN, invalid book presented as verified, lost checkpoint, private log disclosure, unknown write, orphan owned process => FAIL; stop only owned test processes, preserve private evidence |
| G3 30min | CPU/RSS/threads/disk growth, queue depth/drop count, WS reconnect/sequence gaps, last event ages, PG commit latency/errors, UI heartbeat; collect at фиксированный интервал | При нарушении утверждённых bounds — stop; no automatic restart of unknown processes; no promotion to G4 |
| G4 2h | Те же метрики плюс повторный controlled shutdown/restart only owned processes и checkpoint continuity | После G3 PASS требуется новое разрешение; fault injection только в тестовые процессы/DB |
| G5 24h | Устойчивый workload, retention/quota, continuity, CPU/RAM/disk trends, recovery и final read-back | После G4 PASS требуется новое разрешение; duration alone не PASS |

На каждом этапе record: exact source/tree, operator permit/reference, предыдущий gate, UTC start/end/duration, workload, thresholds, actual metrics, stop reason, cleanup ownership, PASS/FAIL/BLOCKED. Нет thresholds или metrics — BLOCKED. Harness никогда не продолжает следующий этап автоматически. Существующий `record-runtime.ps1` возвращает application_health_verdict=NOT_EVALUATED; он не доказывает health/SLA.

## Неподтверждённая реализация

Source содержит public Bybit transport, orderbook/health/storage и checkpoint components; это не physical acceptance. Health endpoint, независимый процесс supervisor/crash recovery, safe immutable installer, end-to-end attestation и полностью автоматизированный G1–G5 harness ещё не приняты. Не открывать новый listening port ради health без review; для G2 сначала выбрать локальный read-only health contract. Подготовка и runtime реализация этих частей продолжаются после устранения G0-блокера; сейчас не запускались UI, collector, Bybit connectivity или PostgreSQL.

**Итог: ADMINIT NO-GO; G0 BLOCKED; G1–G5 NOT_AUTHORIZED/NOT_RUN. Production deployment и merge не выполняются.**
