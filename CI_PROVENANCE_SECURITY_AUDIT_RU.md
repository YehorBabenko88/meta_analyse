# CI_PROVENANCE_SECURITY_AUDIT_RU

Дата: 2026-10-25. Независимый adversarial Security-аудит. Только GitHub metadata, source, опубликованные artifacts и offline анализ. Никаких native/physical тестов, merge, deployment или production DB изменений.

**ADMINIT: NO-GO.** Любой CI/metadata/privacy PASS ограничен доказательствами тестирования и не является разрешением commissioning.

## 1. Замороженные исходные версии

| PR | HEAD | Наблюдение |
|---|---|---|
| #26 | `8885381efa5c65741ae765f55bc230baccbc0ccc` | Metadata gate; синтетические Windows/Linux проверки |
| #27 | `2ecb671aa298c1e47ce304ab48f41ef85cd242a8` | Исходный content gate: XML/exception adversarial FAIL |
| #28 | `15a9d25233cc2383f2f771c0536bb1b1eeaae20a` | Исправления XML projection/error privacy, synthetic PASS |
| #29 | `0c255f4587b1293c8ede22a31636b7d24cfaced2` | Standalone JUnit privacy, не защищает все legacy uploads |
| #30 | `fe9833a3aa9606b04f98f0f655916b83270dfdb3` | Новый кандидат единой публикации; **BLOCKED до полного exact-HEAD CI/artifact review** |

Проверять последующие HEAD заново. Не переносить PASS с прежнего коммита, дерева, run или attempt.

## 2. Независимые результаты

1. PR #30 использует `contents: read` в семи проверенных workflows. В synthetic workflows есть branch/event concurrency. Наличие разрешений в workflow не доказывает настройки репозитория, branch protection и безопасность сторонних actions.
2. В девяти проверенных местах публикации вызов `actions/upload-artifact@v4` ограничен `if: always() && steps.privacy*.outcome == 'success'`, а публикуемый путь — `public-evidence/`. Проверить все реальные attempts и отсутствие иных upload/workflow источников до общего PASS.
3. `project_public_ci_evidence.py` формирует отдельный staging bundle, затем проверяет manifest и переносит его в конечный каталог. Исходные logs, traceback, raw JUnit, process-probe и PostgreSQL logs не входят в заявленный публичный набор. Это проверка кода, не доказательство отсутствия иных каналов публикации.
4. Источник связывается с git HEAD/tree, `GITHUB_SHA`, event/head SHA, run ID, attempt и job. Сам manifest не является цифровой подписью GitHub и не заменяет проверку authenticated artifact ID, API metadata, run/job state и ZIP digest.
5. Реальный artifact **12594881656** из run **40182611622** скачан и проверен: ZIP SHA256 `31ff3f720eb5f048304fe8983b583c8d2a08c599692af9a045ed99a2ad7e2778` совпадает с GitHub API; внутри ровно `junit-000.xml`, `source-sha.json`, `manifest.json`. Manifest указывает HEAD #30, tree `925e1450c847de660bc370644aab7ea389ab8bdb`, run ID `40182611622`, attempt `1`, job `archive-pinned-contract`. Это **один проверенный bundle**, не вся матрица.
6. На момент повторной проверки PR #30: CI #1264 `in_progress`, storage #244 `success`, kernel offline #38 `success`, public JUnit synthetic #10 `success`, content/audit synthetic `skipped`. **In progress/skipped не являются PASS.**
7. Ранее опубликованный full-CI artifact PR #29 содержал hostname metadata в raw JUnit. Новая схема не удаляет уже опубликованные artifacts и не исправляет исторические публикации.

## 3. Adversarial regression acceptance matrix

| ID | Атака / негативный сценарий | Ожидаемое поведение |
|---|---|---|
| A01 | PR merge SHA вместо фактического head SHA | BLOCKED |
| A02 | Source SHA правильный, tree другой | BLOCKED |
| A03 | Смешаны run ID и artifact другого запуска | BLOCKED |
| A04 | Artifact от другого run attempt | BLOCKED |
| A05 | Job skipped/cancelled/queued/missing | BLOCKED |
| A06 | Один обязательный job отсутствует, workflow success | BLOCKED |
| A07 | Неполная пагинация jobs/artifacts API | BLOCKED |
| A08 | Подмена ZIP при сохранении имени artifact | SHA FAIL |
| A09 | ZIP digest API отсутствует или не совпадает | BLOCKED |
| A10 | ZIP содержит лишний файл или duplicate filename | BLOCKED |
| A11 | ZIP path traversal, symlink или Windows reparse | BLOCKED |
| A12 | Manifest с duplicate JSON keys или NaN | BLOCKED |
| A13 | Manifest с подменой source/job/event | BLOCKED |
| A14 | Raw hostname/path в JUnit attributes | Отсутствует в публичном bundle |
| A15 | Raw properties, system-out, system-err | Отсутствуют в публичном bundle |
| A16 | Raw traceback или DSN в failure text | Отсутствует в публичном bundle |
| A17 | XML DTD, entities, comments, PI | BLOCKED |
| A18 | XML глубже лимита, oversized, invalid UTF-8 | BLOCKED |
| A19 | Nested testcase/status hiding | BLOCKED |
| A20 | Противоречивые tests/failures/errors/skipped counters | BLOCKED |
| A21 | Failure превращён в PASS projection | BLOCKED независимым oracle |
| A22 | Skipped обязательный тест переименован | BLOCKED identity oracle |
| A23 | Дублирующиеся test identities | BLOCKED |
| A24 | Пустой/missing JUnit после падения pytest | Нет успешной публикации |
| A25 | Privacy gate падает при `if: always()` | Нет upload; workflow FAIL |
| A26 | Privacy gate PASS, но pytest FAIL | Публикация допустима только как evidence; workflow FAIL |
| A27 | Неудачный rename/write/close stage | Нет частичного публичного bundle |
| A28 | PostgreSQL/server log и raw native JSON | Не публикуются |
| A29 | Изменён исходный manifest тестов | BLOCKED, сверка с immutable expected identities |
| A30 | CI metadata/content/privacy PASS трактуется как ADMINIT GO | Отказ: authorization NONE |

Позитивный P01: полный Windows/Linux synthetic набор с exact SHA/tree/run/attempt, обязательными identities, нулём неожиданных skips и сверенными ZIP digest/manifest. P02: failure в тесте даёт корректный минимальный публичный artifact, но итог workflow остаётся FAIL.

## 4. Необходимые доказательства для PASS нового PR

- Exact HEAD + git tree + source manifest и матрица всех ожидаемых workflow/event/platform/run/attempt/job.
- Все jobs terminal; только обязательные `success`, без скрытых skipped/cancelled/missing.
- Authenticated artifact metadata с полным перечнем и пагинацией, затем загрузка **каждого** обязательного ZIP по ID, сверка GitHub digest и локального SHA256.
- Безопасная инвентаризация ZIP, точные hashes всех manifest files, independent JUnit parser и expected testcase identity oracle; не полагаться на один только count.
- Независимые негативные сценарии A01–A30, в том числе failure-path `if: always()` и rollback staged publication.
- Отдельная проверка GitHub raw logs, failed step output, PostgreSQL stdout/stderr и lifecycle logs на потенциальные утечки; отсутствие в artifact не доказывает отсутствие в raw Actions logs.
- Доказательство сохранения прежних обязательных тестов и отсутствия смягчения CI; separate PG18/Windows results.
- Отдельный human authorization gate для любых реальных испытаний. ADMINIT остаётся NO-GO.

## 5. Вердикт

**PR #30: BLOCKED (не окончательный FAIL)** на указанном HEAD: исправления выглядят направленными на известные утечки, первый реальный bundle проходит ZIP custody и инвентаризацию, но полная Windows/Linux CI матрица и все реальные artifacts ещё не подтверждены. Synthetic `success` не повышается до global PASS.

Никаких изменений PR #26–#30, workflows или GitHub settings этим независимым отчётом не выполнено. Документ находится в отдельной audit-ветке и не разрешает merge/deployment.
