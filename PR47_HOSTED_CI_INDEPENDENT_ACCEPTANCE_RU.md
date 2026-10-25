# PR47_HOSTED_CI_INDEPENDENT_ACCEPTANCE_RU

Дата проверки: 2026-10-25. Независимый read-only GitHub Actions аудит PR #47. **Вердикт BLOCKED; ADMINIT NO-GO.**

## Immutable candidate and provenance

PR #47 Draft, HEAD `59626930a911c0dde330f7760c78ccd99468a1f4`, Git tree `5cff9cedffa5b65f3bfb351e851370ff28d7aca7`. Эти SHA получены независимо через PR API, оба run objects (`head_sha`, `head_commit.tree_id`) и Git commit API. Base `a04f132d64db0981ef93de1be8208612de08a194`. Ветка `integration/adminit-final-20261025`.

## Exact-hosted metadata — API results

| Event | Run ID | Attempt | Job | Job ID | labels | status | runner_id / name | artifacts |
|---|---:|---:|---|---:|---|---|---|---:|
| push | 40203571477 | 1 | synthetic (ubuntu-latest) | 121199663026 | ubuntu-latest | QUEUED | 0 / empty | 0 |
| push | 40203571477 | 1 | synthetic (windows-latest) | 121199663243 | windows-latest | QUEUED | 0 / empty | 0 |
| pull_request | 40203574132 | 1 | synthetic (ubuntu-latest) | 121199671825 | ubuntu-latest | QUEUED | 0 / empty | 0 |
| pull_request | 40203574132 | 1 | synthetic (windows-latest) | 121199671990 | windows-latest | QUEUED | 0 / empty | 0 |

Оба run objects имеют `status=queued`, `conclusion=null`, `run_attempt=1`, корректные event/HEAD/tree. Перечни jobs получены с `per_page=100`, `total_count=2` для каждого; перечислены все jobs. Перечни artifacts: `total_count=0` в каждом run. В API `started_at` не следует считать доказательством фактического запуска, пока `status=queued`, `runner_id=0` и шаги не выполнены.

**ZIP digest: NOT_AVAILABLE. JUnit source identities: NOT_HOSTED_VERIFIED.** Не выдавать локальные 1618 PASS / 2 symlink SKIP за hosted acceptance. Два live-DPAPI cases намеренно deselected, это не PASS.

## Root-cause diagnosis — boundary of evidence

Имеются две независимые очереди event push/PR, но job runner не назначен. В workflow есть `concurrency.group=adminit-final-${{ github.event_name }}-${{ github.head_ref || github.ref_name }}`, `cancel-in-progress:false`. Event-разделение не даёт двум runs той же event конкурировать друг с другом; другие runs по тому же group нужно проверять отдельно. Jobs созданы (trigger guards применились). `contents:read`, checkout uses exact PR head or github.sha. Сведения API `/actions/permissions` и `/actions/runners` недоступны через текущий ограниченный GitHub fetch connector; `rulesets` возвращает пустой список, что не является доказательством отсутствия всех branch protection mechanisms. Billing/quota/runner capacity/admin policy **не установлены**. Никаких изменений GitHub settings, retries или отмен.

## Source contracts examined

`.github/workflows/adminit-final-synthetic.yml`: Windows/Linux matrix, `fail-fast:false`, synthetic env, `--noconftest`, explicit source JUnit plugin; self-contained suite with bounded dependency install. Runs do not define PostgreSQL services or direct native/Bybit execution steps.

`scripts/check_final_integration_junit.py` checks exact opaque source-collected identities, status, source SHA/tree and allows only hashed symlink skips. `integration_synthetic_boundary.py` blocks a subset of `psycopg.connect`, host_identity APIs, subprocess and external sockets via monkeypatch; **not OS containment** and not proof every possible native/DB/network route is impossible. The source-collected expected set is built in the same test environment, so full independent required-test oracle is still valuable.

`if:always()` publication executes project/validate and only uploads `public-evidence/` if `steps.privacy.outcome == success`. The workflow fails on required test gate failure; safe failure publication is permitted only when projector passes. **Failure-path host witness not yet available.** Source-only privacy checks cannot prove actual ZIP contains no hostname, SID/PID, DSN, tokens, paths or traceback.

Full CI/Storage and legacy privacy workflow on this integration branch are intentionally SKIPPED: they do not satisfy hosted PASS or physical acceptance.

## P0/P1/P2 and final acceptance

- **P0 BLOCKED:** both runs must be terminal, all four required jobs SUCCESS and bound to exact SHA/tree/attempt. Queued/cancelled/skipped/missing != PASS.
- **P0 BLOCKED:** source-collected 1620 testcase identities, 1618 actual PASS, precisely two allowed symlink skips, zero failures/errors/unexpected skips, two intentionally deselected live-DPAPI cases not counted.
- **P1 BLOCKED:** real artifact ZIP digest from GitHub API, independent downloaded bytes SHA256, manifest exact inventory/file hashes and SHA/tree/run/attempt/job, no stale/mismatched artifacts, no symlink/path traversal/duplicate entry.
- **P1 BLOCKED:** public XML strict projection/privacy and malformed XML/JSON/DTD/entity expansion/UTF16/UTF32, sensitive fields; raw Actions logs must be separately examined.
- **P1 BLOCKED:** failure-path privacy and end-to-end synthetic boundary proof; source-only tripwires are not a sandbox.
- **P2 OPEN:** authenticated administrative scheduling investigation; no evidence for billing/quota/runner availability hypothesis. Check Actions UI warnings, repo/org Actions settings, usage and runner inventory read-only.
- **P0 POLICY:** even future hosted synthetic PASS does **not** authorize ADMINIT physical G0/G1, DB modifications, live native/Bybit, trading or deployment.

## Recovery sequence

(1) Obtain read-only Actions diagnostic banners/admin evidence for queue; (2) leave workflow gates intact; (3) verify terminal jobs by exact run/attempt; (4) download two ZIPs per event via authenticated artifact IDs; (5) compare GitHub digest, local SHA256, manifest and JUnit source identities, privacy; (6) issue PASS only if all contracts pass; otherwise FAIL/BLOCKED. Do not rerun or modify code to skip checks.

This report is independent and published only on a separate audit branch. No merge, deployment, physical/native/PG/Bybit activity performed.


## 2026-10-25: repeat read-only verification and scheduling diagnostics

PR API still reports HEAD `59626930a911c0dde330f7760c78ccd99468a1f4`. Fresh authenticated run metadata for push `40203571477` and PR `40203574132` independently confirms identical `head_commit.tree_id=5cff9cedffa5b65f3bfb351e851370ff28d7aca7`, `run_attempt=1`, `status=queued`, `conclusion=null`. Job-list `total_count=2` for each run, labels `ubuntu-latest` and `windows-latest`, `runner_id=0`, empty `runner_name`; artifact-list `total_count=0`. No ZIP digest or hosted JUnit exists to verify.

Repo rulesets endpoint returned `[]`, but Actions permissions, runner inventory and branch protection administrative endpoints are not accessible through this GitHub connector; absence of rulesets does **not** prove that all protections are absent. Official GitHub troubleshooting documentation notes that runner limits, billing restrictions and stuck concurrency/check-suite state are possible categories; **none is demonstrated as the cause of these exact two runs**. The workflow groups are separated by event name (`push` versus `pull_request`), so the two required runs do not share an identical group; other runs/groups and administrative constraints require independent evidence.

Safe escalation: inspect read-only Actions run warnings and Settings > Actions > Runners (active/queued job usage), repository/organization policy and usage; if GitHub shows stuck or inconsistent scheduler/check-suite state, send the two run IDs, job IDs, UTC creation times and runner_id=0 evidence to GitHub Support. Do not retry/cancel/change gates without explicit coordination.

Source review limitation: `integration_synthetic_boundary.py` uses pytest autouse monkeypatches, not OS isolation; `check_final_integration_junit.py` verifies the actual source-collected set, but the expected set is produced within the same pytest collection, so a separate frozen mandatory-case oracle remains desirable. `if: always()` privacy upload is conditional on projector success; this does not independently prove a hosted failure-path witness.

**Updated verdict: BLOCKED / ADMINIT NO-GO.** No hosted test outcomes, artifact digest or privacy runtime acceptance can be claimed. No retry, merge, deployment, native, PostgreSQL or Bybit execution.
