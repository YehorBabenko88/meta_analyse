# META_ANALYSE_CI_FINAL_ACCEPTANCE_RU

Дата проверки: 2026-10-25. Независимый CI/CD Security / Privacy / Provenance audit. **ADMINIT NO-GO.** Только read-only GitHub inspection; отчёт размещён в отдельной audit-ветке. Ни merge, deployment, native/physical тестов, ни production DB изменений.

## 1. Exact-HEAD матрица PR

| PR | HEAD | Hosted evidence |
|---|---|---|
| #33 | `47a727c34f6894e2f844741487bb0ac5d571cb75` | CI `40187337989`, Storage `40187338056`, Windows ABI source `40187338030` — QUEUED |
| #34 | `f80469ebb174d402e56c91724c120324c8567bce` | CI `40200047303`, Storage `40200047383`, Kernel `40200047215` — QUEUED; 3 maintenance synthetic policy-SKIPPED |
| #35 | `e4bc8bd6a1faa7103244423bd0b00948bad8dba2` | CI `40200166949`, Public Bybit E2E `40200166782` — QUEUED |
| #41 | `5b622cc218fdf90d26164d544176dd647297fc53` | Native SCM PR `40198867909` — QUEUED; CI/Storage policy-SKIPPED |
| #42 | `cef0155fc1fa1a5d031908bde7f54369f34a8b55` | CI `40200057193`, Storage `40200057172`, Native SCM `40200057178` — QUEUED |
| #43 | `a04f132d64db0981ef93de1be8208612de08a194` | **Push `40200317121`, PR `40200322626` — QUEUED**, CI `40200322602` и Storage `40200322669` policy-SKIPPED |

PR #43 tree из PR description: `d9b0c63525bb8bc28464002e676caee5a5ce626e`. Это исходное утверждение автора, не независимо подтверждённый hosted manifest. Никакие PASS старых SHA не переносятся.

## 2. PR #43: jobs, attempts, artifacts

| Run | Job ID | OS | Status |
|---|---:|---|---|
| Push 40200317121 | 121189915822 | Windows | QUEUED |
| Push 40200317121 | 121189915962 | Ubuntu | QUEUED |
| PR 40200322626 | 121189932879 | Windows | QUEUED |
| PR 40200322626 | 121189932961 | Ubuntu | QUEUED |

Artifacts по обоим run: **0**. Run attempts и полные run event/head SHA receipts требуют прямого GitHub REST/UI подтверждения: доступный connector возвращает jobs без `run_attempt`. Отсутствуют hosted JUnit, ZIP digest, source manifests, job output и runtime test identities. Поэтому вердикт **BLOCKED**, не PASS и не тестовый FAIL.

## 3. Причина длительного QUEUED

Из доступного GitHub API доказано: четыре job созданы и находятся в QUEUED; runner assignment/started_at отсутствует. Нет подтверждения billing, quota, runner capacity, org restrictions или concurrency. Connector не предоставляет административные Actions runner/billing/branch protection endpoints. Причина не установлена.

Для восстановления: администратор проверяет GitHub Actions run UI banners, repository Settings > Actions > General, org Actions policies, runner availability/usage/billing/quota и branch protection/required checks. Сохраняет timestamps, runner/job metadata и скриншоты/экспорт. Без подтверждённой причины не менять настройки и не выполнять массовые reruns.

## 4. Trigger, permissions, checkout, publication

На exact PR #43 `.github/workflows/native-scm-adapter-synthetic.yml`: push branches включают `parallel/adminit-scm-correlation-20261025`, PR paths включают изменённые commissioning/тесты/workflow; jobs не имеют дополнительного `if`. Matrix Ubuntu/Windows, `fail-fast: false`, `contents: read`, checkout `github.event.pull_request.head.sha || github.sha`, Python 3.12. Frozen predicate oracle fetch использует SHA `4a92643c00a7e4d113025e1df427d8f4850f0981` без смены HEAD. Обязательный JUnit gate: минимум 338, критические имена, только явный capability skip `test_symlink_is_rejected`.

Full `ci.yml` и `storage-ingestion.yml` содержат branch exclusion guard для `parallel/adminit-scm-correlation-20261025`: их SKIPPED ожидаемы для узкого synthetic PR и **не заменяют** полный интеграционный gate. При переносе изменений в интеграционную ветку обязателен полный Windows/Linux/PG18 CI на новом SHA.

`if: always()` privacy projection создаёт только `public-evidence/`, upload разрешён только при `steps.privacy.outcome == 'success'` и `if-no-files-found: error`. Наличие source-кода не подтверждает failure-path runtime semantics; при pytest FAIL workflow должен оставаться FAIL.

## 5. P0/P1/P2 acceptance matrix

| Severity | Контроль | Verdict |
|---|---|---|
| P0 | PR43 push/PR Windows+Linux hosted execution | BLOCKED (4 QUEUED) |
| P0 | Exact SHA/tree/run/attempt/job/artifact custody | BLOCKED (нет artifacts) |
| P0 | Required JUnit identities/status, отсутствие ложного PASS | BLOCKED (нет hosted JUnit) |
| P0 | CI PASS не разрешает physical ADMINIT/deployment | NO-GO enforced by audit policy |
| P1 | ZIP SHA256, manifest file inventory, source binding | BLOCKED (0 artifacts) |
| P1 | Hostname/SID/username/paths/DSN/tokens/traceback privacy | SOURCE REVIEW ONLY |
| P1 | XML/JSON DTD/entity/UTF-16/UTF-32/duplicate keys/depth | SOURCE REVIEW ONLY |
| P1 | Failure-path `if: always()`, incomplete staged output | BLOCKED (нет hosted witness) |
| P1 | Все upload-artifact sites / отсутствие raw fallback | Требует полного нового exact-HEAD inventory |
| P2 | Repo/org runner/concurrency/branch protection policy | BLOCKED (нет admin evidence) |
| P2 | Historical ZIP exposure и SHA256 case pseudonym dictionary risk | OPEN |

## 6. Независимая hosted приёмка после восстановления очереди

1. Заморозить HEAD, git tree, event, run ID, attempt и все job IDs. Убедиться, что обязательные jobs terminal SUCCESS, а policy SKIPPED отмечены как NOT_APPLICABLE, не PASS.
2. Скачать оригинальные ZIP **по authenticated artifact ID**, сверить ZIP SHA256 с GitHub API, исключить duplicate names, symlink/path traversal, extra/missing files.
3. Проверить manifest SHA/tree/run/attempt/job, exact inventory и каждый file digest; source receipt не является самостоятельной подписью GitHub.
4. Сверить исходные testcase identities с независимым expected oracle, counts, failures/errors/skips и Linux capability skip; не принимать только общее число тестов.
5. Проверить projected JUnit на hostname, SID, paths, DSN, tokens, traceback, properties, system-out/err и XML DTD/entities/encoding smuggling. Проверить raw Actions logs как отдельный канал утечки.
6. Проверить failure-path: тест падает, privacy projector сохраняет фактический FAIL и публикует только безопасный bundle, workflow остаётся FAIL. При отсутствии input или отказе projector — нет upload.
7. Повторить полный Windows/Linux/PG18/Storage/Kernel offline CI на интеграционном exact HEAD. CI PASS не повышает ADMINIT G0/G1.
8. После нового Codex PR начать проверку с нуля на его фактическом HEAD. Не использовать fixtures вместо hosted evidence.

**Финальный вердикт: PR #43 BLOCKED (QUEUED), ADMINIT NO-GO.** Нет доказанного application failure, нет оснований ослаблять gates или применять `skip-ci`.
