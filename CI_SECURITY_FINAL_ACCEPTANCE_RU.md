# CI_SECURITY_FINAL_ACCEPTANCE_RU

Дата: 2026-10-25. Независимая Security-приёмка CI/CD `YehorBabenko88/meta_analyse`. Работа read-only по PR #30; изменения отчёта — только в собственной audit-ветке. **ADMINIT NO-GO.**

## 1. Exact HEAD

- PR #30: `6d01bf3d9f4118ac336624c9986c4ed876edd445`.
- Tree по независимому интеграционному аудиту: `d9d20ddb7f5979816d6de4cbf6819fcaef19bf2d`. Подтверждение tree в новых artifacts ещё невозможно.
- От предыдущего `346b9fbfcf293d3745920240e530b76fd03ebb07` изменены только `.github/workflows/ci-audit-synthetic.yml`, `.github/workflows/ci-content-review.yml`, `docs/PUBLIC_CI_EVIDENCE_HARDENING.md`. Новые workflow разрешают аудит на `audit/public-evidence-transaction-20261023`.
- Успешные результаты старых HEAD не засчитываются за новый.

## 2. GitHub Actions — фактическое состояние

| Workflow | PR run | Jobs | Статус |
|---|---:|---|---|
| CI | 40185408459 | windows, linux, archive-pinned-contract | QUEUED |
| Storage ingestion | 40185408595 | integration | QUEUED |
| Kernel identity offline | 40185408451 | ubuntu, windows | QUEUED |
| Public JUnit privacy synthetic | 40185408614 | ubuntu, windows | QUEUED |
| CI audit synthetic | 40185408492 | ubuntu, windows | QUEUED |
| CI content security synthetic | 40185408596 | ubuntu, windows | QUEUED |

Все 12 jobs на перечисленных PR runs QUEUED; runner assignment отсутствует в доступном ответе. Никаких exact-HEAD terminal JUnit/ZIP/manifest artifacts пока нет. Это **CI BLOCKED**, не тестовый FAIL и не PASS.

### Причина QUEUED

Подтверждён только факт отсутствия назначения runner на момент проверки. Нельзя достоверно отличить billing/quota/лимиты, GitHub runner capacity, ограничения concurrency или другие scheduling причины по одному статусу QUEUED. Для установления причины нужны GitHub Actions UI/административные billing/runner/usage сведения либо соответствующее API evidence. Не приписывать причину без источника; не делать массовый rerun и не менять настройки без согласования.

## 3. Source security audit

- Семь workflow definitions, девять upload-sites: источник PR #30 публикует staged `public-evidence/` после успешной privacy projection; права `contents: read`. `if: always()` позволяет безопасную публикацию failure evidence, но не превращает pytest FAIL в workflow PASS.
- Checkout использует PR head SHA, source receipt связывает git SHA/tree, event SHA, run ID, attempt и job. Независимый verifier должен проверить GitHub API metadata, artifact ID и digest; self-reported manifest не является GitHub-подписью.
- Raw JUnit projection отбрасывает hostname, username/path, properties, system-out/system-err, traceback; failure/error/skip сохраняются как статусы и агрегированные счётчики. Контракт на новом HEAD пока подтверждён только чтением исходников, не exact-HEAD hosted artifacts.
- XML parser запрещает DTD, PI, comments, NUL, alternate encoding smuggling; тесты UTF-16 LE/BE присутствуют. Независимо проверить UTF-32, BOM, malformed counters, deep nesting и entity expansion.
- ZIP SHA256, inventory, manifest hashes и source provenance ранее успешно проверены для восьми ZIP HEAD `fe9833a3` и нескольких ZIP `346b9fb`, но это **исторические результаты**, не evidence HEAD `6d01bf3`.
- Raw Actions logs остаются отдельным каналом возможной утечки. Старые опубликованные ZIP не удалены и не переписаны PR #30.

## 4. Severity / acceptance matrix

| Приоритет | Проверка | Статус на HEAD 6d01bf3 |
|---|---|---|
| P0 | Exact SHA/tree/run/attempt/job/artifact ZIP custody | BLOCKED — runs QUEUED |
| P0 | Полная Windows/Linux/PG18/Storage/Kernel матрица | BLOCKED — runs QUEUED |
| P0 | Failure-path privacy при `if: always()` | BLOCKED — нет hosted witness |
| P0 | Запрет deployment/ADMINIT на основании CI PASS | PASS по заявленному policy; физический gate NO-GO |
| P1 | Raw hostname, DSN, username, paths, traceback отсутствуют во всех новых ZIP | BLOCKED — artifacts отсутствуют |
| P1 | JUnit failures/errors/skips и exact required identities | BLOCKED — raw-to-public oracle отсутствует |
| P1 | XML UTF-16/32, DTD, entities, nested/malformed counters | SOURCE REVIEW; hosted tests QUEUED |
| P1 | Все девять upload-sites, включая failure и missing input | SOURCE REVIEW; hosted proof отсутствует |
| P1 | Raw logs/PG output/lifecycle reports не раскрывают private data | BLOCKED — нет нового run logs |
| P2 | Branch/event/concurrency/permissions/checkout policy | SOURCE REVIEW; admin settings не проверены |
| P2 | Псевдонимы testcase SHA256 устойчивы к словарному перебору | OPEN RISK — SHA256 не анонимизация |
| P2 | Historical artifacts и срок хранения | OPEN RISK — старые публикации не исправлены |

## 5. Обязательные adversarial сценарии

1. Подмена source/tree/event/run/attempt/job/artifact, ZIP digest, duplicate ZIP entries, path traversal.
2. Missing, skipped, queued, cancelled, failure jobs и неполная пагинация API.
3. DTD, entities, UTF-16 LE/BE, UTF-32 LE/BE, BOM/NUL, malformed XML, nested testcases, mismatched counters.
4. Failure/error/skip status promotion, duplicate/missing required testcase, JUnit classname spoofing.
5. Privacy gate failure на `if: always()`, отсутствие input, частичный staging, rename failure, repeated cancellation.
6. Raw hostname, username, DSN, filesystem paths, traceback, PostgreSQL output, lifecycle logs и raw Actions logs.
7. Полная независимая сверка expected test identities и source manifest, включая разрешённый Linux installer skip.
8. Проверка, что любой CI metadata/content PASS имеет authorization NONE для ADMINIT и deployment.

## 6. Критерии финального PASS

Только после terminal exact-HEAD runs: все обязательные jobs success; отсутствие неожиданных skips; загрузка каждого ZIP по artifact ID; SHA256 по API; строгая проверка inventory и manifest; независимый raw-to-public JUnit identity/status oracle; безопасная публикация failure evidence; проверка logs и отсутствие новых утечек. Отдельная physical authorization обязательна даже после CI PASS.

**Вердикт сейчас: BLOCKED. ADMINIT NO-GO.** Не выполнялись merge, deployment, native/physical tests, production DB changes или изменения PR #30.
