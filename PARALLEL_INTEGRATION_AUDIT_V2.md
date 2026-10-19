# PARALLEL INTEGRATION AUDIT V2

Дата: 19 октября 2026, Europe/Berlin. **Рекомендация: NOT READY.**

Исходники агентов не исправлялись. Аудит выполнялся в отдельном checkout
`work/parallel-integration-audit-v2`, ветка `audit/parallel-integration-v2-20261019`.
Main, агентские ветки и LS5 не изменялись; merge и развёртывание не выполнялись.

## Границы и исходный отчёт

Первоначального `PARALLEL_INTEGRATION_AUDIT.md` в checkout не было. После запроса
пользователь явно отменил требование его проверять: «не проверяй его ... продолжай
как считаешь нужным, проверь все файлы в проекте». Поэтому буквальное сравнение с
первоначальными формулировками и первоначальными отрицательными тестами невозможно.
Ниже R1–R7 — **рабочая реконструкция направлений по PR/коммитам**, а не цитата
отсутствующего отчёта. R1, R3 и R6 прямо упоминаются в описании PR8 и истории;
смысл остальных номеров сгруппирован для воспроизводимого повторного аудита.

Инвентаризированы и прочитаны программно все **180 отслеживаемых файлов** PR10;
для **164 Python-файлов** выполнен AST/syntax check. Пофайловые SHA-256 находятся
в [file-manifest.json](audit_v2/file-manifest.json). Ручная семантическая проверка
сосредоточена на архивах, SQL/импорте, Order Flow, Qt/async lifecycle, packaging,
фикстурах и workflows; полный pytest проверяет проект совместно. Это не утверждение
о формальном доказательстве корректности каждой строки или полной веточной coverage.

## Зафиксированные HEAD

| PR | Направление | Точный проверенный HEAD |
|---|---|---|
| 6 | Archive Reliability | `ad672fed702ecdb29f228886acd14b60a367d3bd` |
| 7 | Order Flow | `bd26d8a30b6dc39144585d8f5ec0340afedc8618` |
| 8 | PostgreSQL | `340bad1d016a0f6e30bfe575ab90ae3e4db7a3fa` |
| 9 | Integration CI | `083fe42a515da49d2c47e2e631b2e11478d2bdbe` |
| 10 | Общая сборка | `aa489666191137b631aab989f4834743820f4831` |

Перед завершением повторная GitHub-проверка подтвердила те же пять HEAD.
Не использовалась проверка одного лишь ancestry: PR10 собирался синхронизацией
файлов, поэтому сравнивались git blobs каждого изменённого агентом пути.

## R1–R7: результаты отдельно

| Пункт, рабочее направление | Статус | Доказательство и предел вывода |
|---|---|---|
| R1 — PostgreSQL → Order Flow → Desktop | **FIXED** | Реальный двухстрочный gzip передан через локальный HTTP, acquire/audit/receipt, настоящий PostgreSQL, worker-owned load и нажатие Qt Load history. История и Order Flow появились, Decimal сохранён, качество UNVERIFIED. Ошибка terminal-status ниже — отдельная регрессия. |
| R2 — отмена/interprocess lock и ресурсные ограничения архивов | **FIXED** | Ожидание lock асинхронное; acquired-флаг исключает unlock чужого lock. Отмена не оставляет lock. Thread workers ожидаются до освобождения lock. Архивные бюджеты и HTTP fault/resume проверки сохранены. Дополнительное усиление cache-day consistency описано ниже. |
| R3 — согласованность CSV-валидации и точность временных границ | **PARTIAL** | Проверки обязательных/дублирующих колонок, конечных чисел, стороны и порядка есть. Но size=0 аудитор отвергает, importer принимает; Decimal-масштабирование timestamp округляет до усечения. Четыре собственных отрицательных теста падают. |
| R4 — большая история без потери сделок, включая путь пользователя | **PARTIAL** | 100k-trade aggregation сохраняет объёмы; сервис отвергает переполнение вместо молчаливого усечения. Но реальный UI всегда использует limit=5000 и не предлагает лимит/пагинацию. В отдельном FakeStore-воспроизведении 100k строк UI/default-путь отказывает, а прямой API с limit=100000 агрегирует все строки. |
| R5 — immutable snapshots, Qt и stale async results | **FIXED** | Frozen history/trade/row, tuple и readonly mappings; generation guard; source scope/status проверяются; оба UI-tab сохранены. 10k-row/immutable UI и целевые тесты проходят, обычный реальный сквозной путь проходит. |
| R6 — failed checkpoint, rollback/resume и исходная ошибка БД | **FIXED** | Все 9 PostgreSQL-тестов реально выполнены. Собственный тест вызывает настоящий CheckViolation, затем ошибки failed-checkpoint и advisory-unlock: наружу выходит исходный CheckViolation. После failed batch checkpoint=1/status=failed; после устранения конфликта повтор импортирует с позиции 1, заканчивает checkpoint=2/status=imported без дублей. |
| R7 — fail-closed обязательные интеграционные CI-gates | **OPEN** | Из PR9 отсутствуют verifier и его тест; workflow PR10 совпадает с PR6, не PR9. Основной зелёный CI пропускает 9 PostgreSQL cases. Отдельный storage workflow их выполняет, но не заменяет потерянную проверку полноты/JUnit общего прогона. |

## Что именно вошло из четырёх веток

Полная машинная матрица: [branch-comparison.json](audit_v2/branch-comparison.json).
Сравнение ограничено путями, изменёнными каждой агентской веткой относительно её
merge-base с общей исходной веткой, а не посторонними изменениями других агентов.

| PR | Идентичны HEAD агента | Отличаются | Отсутствуют | Вывод |
|---|---:|---:|---:|---|
| 6 | 18 | 2 | 0 | Основные archive-модули свежие. В archive_ingestion.py удалён избыточный upper-bound first_ms: last>=first и last<max оставляют ту же гарантию. Но отсутствует последняя 23-строчная параметризованная регрессия out-of-range first timestamp из tests/test_archive_ingestion.py. |
| 7 | 13 | 2 | 0 | Core metrics/adapters/aggregation/view и тесты свежие. Отличаются только desktop.py/desktop_service.py из-за объединения с PR8. |
| 8 | 7 | 3 | 0 | Импорт, миграции, storage reader и storage-тесты актуальны. Два desktop-файла объединены с PR7, в test_flow_history_storage.py добавлены integration guard/bridge проверки. |
| 9 | 0 | 1 | 2 | Не перенесены scripts/check_integration_junit.py и tests/test_integration_contract_ci.py. .github/workflows/ci.yml заменён версией PR6. |

Следовательно, **PR10 не содержит актуальный результат всех четырёх агентов**.
Это не просто «старый общий код»: PR7/PR8 содержательно сохранены и соединены,
PR6 почти совпадает; конкретная потеря относится прежде всего к PR9 и последнему
регрессионному тесту PR6.

### Пересечение desktop.py / desktop_service.py: PR7 × PR8

В PR10 сохранены оба интерфейса: Flow History (PR8) и Order Flow History (PR7).
Сохранены snapshot-поля, immutable rows и запрос с явными symbol/[start,end).
Добавлен мост `to_orderflow_records` после проверок типа, scope, статуса и generation.
Truncated history явно блокирует агрегацию; данные не выдаются за полный интервал.

Пересечение проверено диффами [PR7](audit_evidence_v2/pr7-desktop-overlap.diff) и
[PR8](audit_evidence_v2/pr8-desktop-overlap.diff), 63 целевыми offscreen-тестами
и собственным HTTP/PostgreSQL/Qt сценарием. Найдена регрессия terminal-status ниже.

### Пересечение ci.yml: PR6 × PR9

Blob ci.yml у PR10 и PR6 одинаков: `f68951babbd04ee378c9657adafb82281337d789`.
Из PR9 потеряны `.[test,archive]`, baseline/JUnit completeness gates и отдельный
archive-contract job с требованием конкретных модулей/запретом skips. PR6 добавляет
обязательный aiohttp import и локальные HTTP fault tests; поэтому архивные тесты
в текущем CI действительно исполняются, несмотря на установку extras по частям.
Проблема — потерянная fail-closed проверка и неполный общий PostgreSQL-прогон.

## Независимые дефекты и регрессии

### B1. Потеря PR9 и неполный основной CI — блокирует READY

Два файла отсутствуют, workflow не содержит verifier. В JUnit основного PR10:
Windows **509 passed / 9 skipped**, Linux **508 passed / 10 skipped**.
Девять общих skips — весь test_storage_ingestion_postgres.py, потому что основной
workflow передаёт только META_ANALYSE_TEST_ADMIN_DSN, а модуль требует
META_ANALYSE_TEST_DSN. Десятый Linux skip — ожидаемый Windows installer.

Важно: отдельный Storage ingestion integration workflow действительно запускает
этот модуль и даёт **71 passed**. Поэтому нельзя утверждать, что PostgreSQL вообще
не тестировался. Однако общий прогон пропускает обязательные cases, а потерянные
PR9 gates не дают CI обнаружить это как ошибку интеграционного контракта.

### B2. Timestamp округляется перед усечением — блокирует временной контракт

- `bybit_archive_audit.py:63`: `int(raw_ts * 1000)` использует текущую Decimal
  precision до int. `1735775999.999999999999999999999` становится
  `1735776000000` ms — следующим UTC-днём.
- `archive_db_import.py:57`: ROUND_DOWN применяется после уже округлённого
  умножения. `1735689600.000000999999999999999` импортируется как
  `2025-01-01T00:00:00.000001Z`, хотя усечение должно дать `.000000`.
- Допустимый raw timestamp `253402300799.99999999999999999` аудитор признаёт valid,
  но формирует first_ms за поддерживаемой верхней границей.

Это воспроизводится на более точных дробях, разрешённых текущим валидатором;
обычные six-digit Bybit timestamps этими примерами не объявляются сломанными.
Нужно либо точно масштабировать/усекать без context rounding, либо явно ограничить
поддерживаемую точность входа. Одного наличия Decimal недостаточно.

### B3. Зависший визуальный Loading после терминального исхода

`desktop_service.py:250` устанавливает orderflow_status=Loading. В ветках store=None
(:253), exception (:286) и cancellation (:282) обновляется только общий status.
`desktop.py:408` продолжает показывать Loading history в Order Flow History.
Все три независимых теста падают. Данные/состояние UNVERIFIED не повышаются,
но пользователь получает неверное состояние операции. Исправить до READY.

### Дополнительные ограничения, не равные удалённому обходу безопасности

- Аудитор требует size>0, importer/SQL допускают size=0. Согласовать или явно
  разделить контракты; сейчас тест согласованности падает.
- UI не даёт управлять history limit=5000. Прямой API допускает до 100k (проверено с FakeStore);
  чистый 100k aggregation проходит, но это не доказательство реального PostgreSQL/Desktop пути на 100k.
- `_load_receipt` проверяет day-tag, SHA/размер и числовые границы, но не проверяет
  соответствие first/last указанному дню. Искажённый локальный JSON с day=2025-01-01,
  first=last=1735603200000 (2024-12-31) принимается. Нормальная запись receipt
  этого не создаёт; это hardening локальной metadata-consistency, не remote bypass.
- Неиспользуемый реальным UI `orderflow_archive_reader.py` возвращает mutable list
  и применяет LIMIT без truncation metadata. Текущий UI использует безопасный
  read_flow_history; не подключать старый reader без доработки контракта.

## Интеграционные испытания и JUnit

| Проверка | Результат | Evidence |
|---|---|---|
| Windows 11 / Python 3.12.15, .[test,archive], оба DSN | **518 passed, 0 skipped**, 172.70 s, exit 0 | windows-full.xml/log, windows-full-proof.json |
| Независимые Windows checks | **8 failed, 4 passed**, 3.87 s | windows-independent.xml/log |
| Linux / Python 3.12, PostgreSQL 17.6, .[test,archive], оба DSN | **517 passed, 1 skipped**, 20.63 s | linux-full.xml/log, linux-full-proof.json |
| Независимые Linux checks | **8 failed, 4 passed**, 0.94 s | linux-independent.xml/log |
| Дополнительные archive-focused проверки | **100 passed**, пересекаются с full suite | Независимое read-only ревью; не прибавлять к числу уникальных cases |
| Целевые storage/Qt/Order Flow проверки | **63 passed**, пересекаются с full suite | Независимое read-only ревью |

Все XML и журналы сохранены в [audit_evidence_v2](audit_evidence_v2/junit-summary.json).
Оба full-proof JSON подтверждают исполнение **всех девяти PostgreSQL cases**.
Единственный Linux skip — Windows-only installer. Все архивные зависимости и Qt
установлены; importorskip не скрывает обязательные архивные/Qt тесты.

Восемь падений совпадают по именам на Windows/Linux: 3 timestamp-boundary, 1 zero
quantity consistency, 3 terminal-status и 1 отсутствующий PR9 gate. Они не помечены
xfail, не подавлены и не превращены в warnings; независимый audit job красный
именно из-за найденных дефектов, а не из-за установки, PostgreSQL или flaky timeout.

Четыре успешных собственных сценария:

1. Отмена contended archive lock и немедленное последующее приобретение.
2. Настоящий локальный HTTP gzip → acquire/audit/receipt → PostgreSQL import →
   повторный import → worker service → Qt Load history → history/Order Flow tables.
3. Настоящий DB CheckViolation + ошибка маркировки failed + ошибка advisory unlock:
   наружу выходит исходная DB ошибка, а не cleanup RuntimeError.
4. Failed второй batch сохраняет первый checkpoint; после устранения конфликта
   тот же SHA продолжается с позиции 1 и завершается без дублей.

## GitHub Actions и происхождение SHA

- [Основной CI PR10](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39303416750):
  run.head_sha=aa489666191137b631aab989f4834743820f4831, success; checkout был
  synthetic PR merge `2516fa4`, объединяющий aa48966 с main `2317c79d78654d8006d99b914532a089554677da`.
- [Push CI PR10](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39303393469):
  head_sha=aa489666191137b631aab989f4834743820f4831, success.
- [Storage PR10](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39303416635):
  success, 71 passed; в этом workflow нет JUnit-артефакта, использован job log.
- [Собственный Linux audit](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39305707758):
  push SHA `9e6ce6baf60caae2a29e56b4f5716f59d78cca4a`; full suite и mandatory JUnit
  proof проходят, затем negative suite даёт 8 failed / 4 passed, workflow=FAILURE.
  Guard `git diff --exit-code aa48966 -- src tests scripts pyproject.toml requirements.lock`
  и обе исходные workflow-конфигурации подтверждает неизменность продукта PR10.

Локальный Windows full suite запускался прямо из checkout aa48966. Audit branch
добавляет только собственные проверки, manifest/evidence, отдельный audit workflow
и этот отчёт. Результаты не приписываются коду другой агентской ветки или будущему HEAD.

## Воспроизведение

В отдельном checkout aa489666191137b631aab989f4834743820f4831:

```text
python -m venv .venv
python -m pip install -c requirements.lock -e ".[test,archive]"
python -m pip check
QT_QPA_PLATFORM=offscreen
PYTHONASYNCIODEBUG=1
META_ANALYSE_TEST_ADMIN_DSN=<одноразовый PostgreSQL admin DSN>
META_ANALYSE_TEST_DSN=<одноразовый PostgreSQL ingestion DSN>
python -m pytest tests -q -W error::RuntimeWarning --junitxml=full.xml
python audit_v2/verify_junit.py full.xml
python -m pytest audit_v2 -q -W error::RuntimeWarning --junitxml=independent.xml
```

Последняя команда **должна сейчас завершиться exit 1** с указанными восемью
падениями. Тесты находятся в audit branch, продуктовые источники не исправлены.
Создавались только одноразовые локальные/CI базы; тестовые DELETE/constraints
выполнялись только внутри них. Сетевые запросы ограничены mock/loopback.

## Что требуется перед READY

1. Согласованно перенести актуальные PR9 gates в PR10, не потеряв обязательные
   HTTP fault tests PR6; выставить обе DSN и fail-closed проверять пропуски.
2. Исправить/ограничить точность timestamp-преобразований и согласовать CSV profile;
   повторить отрицательные проверки, не ослабляя их.
3. Публиковать terminal Order Flow status при unavailable/error/cancel.
4. Определить поддерживаемый пользовательский large-history путь (limit/paging
   или явное ограничение UI); вернуть удалённую последнюю регрессию PR6.
5. Повторить Windows/Linux full suites и независимые invariants на новом общем
   **точном SHA**, сохранить JUnit и убедиться, что обязательные cases не skipped.

До этого **NOT READY для интеграции**. Это рекомендация аудита, не merge,
не deployment и не разрешение на live trading. Живая биржа, реальные ордера и
пользовательские уровни MetaScalp не использовались и не изменялись.
