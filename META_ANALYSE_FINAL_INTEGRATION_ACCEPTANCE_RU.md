# MetaAnalyse: независимая security/readiness-приёмка PR47

## Статус и источник

Аудируемая база: PR47 HEAD `59626930a911c0dde330f7760c78ccd99468a1f4`, tree `5cff9cedffa5b65f3bfb351e851370ff28d7aca7`, merge-base с PR43 `a04f132d64db0981ef93de1be8208612de08a194`. Новая ветка `integration/adminit-security-readiness-20261025`; PR47 и исходные PR не изменяются. Окончательные новые SHA/tree/base/merge-base, exact-candidate тесты и ссылки нового Draft PR фиксируются в accompanying dated acceptance receipt после commit; не использовать SHA базы как доказательство нового кандидата.

**Source/offline acceptance — bounded. Hosted acceptance BLOCKED до реальных артефактов. Physical ADMINIT/G0/G1–G5 NOT_RUN/NO-GO.** Ни native collector, ни live DPAPI, ни PostgreSQL на ADMINIT, ни публичный Bybit probe не запускались.

## Полнота review

Все36изменённых путей PR47 учтены в [file-level coverage](docs/PR47_SOURCE_REVIEW_COVERAGE_RU.md). Это учёт source review, не measured line/branch coverage. Независимые reviewers проверили PG, Bybit/worker и CI/Windows boundaries; root отдельно проверил Desktop/health, source gates и public output transaction. Проверены актуальные Git objects и source ancestry. PR48 source substring guards не выданы за native ABI/runtime proof. Из PR50 выбран полезный repeated-cancellation/failed-commit witness; дублирующие toy tests не импортировались. PR49 default control-permission refusal hypothesis не подтверждена primary REL_18_1 source и не стала основанием для ненужных grants.

## Подтверждённые дефекты и исправления

| Severity | Нарушенный invariant / RED | Минимальное исправление |
|---|---|---|
| P1 | Encrypted PGDATA/role binding использовал assert, отключаемый -O | Явные исключения до provisioning; port exact int |
| P1 | Bootstrap SQL не сравнивал независимый file-control system identifier до CREATE | pg_controldata нового PGDATA до start, canonicalID, SQL source/catalog binding перед DDL |
| P1 | Failure cleanup останавливал процесс по mutable path/$started | Удалён auto-stop; UNKNOWN process/partial PGDATA сохраняется для manual ownership review |
| P1 conditional | SET LOCAL identity path истекал до caller SQL | Отдельно committed session catalog path, затем idle connection; witness начинает свой READ ONLY transaction |
| P1 viability | inet::text включает /32, поэтому корректный loopback ошибочно не совпадал с127.0.0.1 | pg_catalog.host(inet_server_addr()) в attestation/controller/realtest; сравнение exactIPv4 сохранено |
| P1 | Raw parser допускал nonfinite prices/sizes и coercion идентичности/времени | Finite positive decimal strings, exact positive int timestamp, nonempty stringID/symbol/topic binding |
| P2 | Book timestamp coercion, probe update-ID regression, duplicate start | Строгие timestamps; обе sequence/update-ID проверки; повторный start отклоняется |
| P2 | DB rollback не увеличивал health gap | Gap до распространения ошибки, без telemetry promotion |
| P2 | При disconnect старые rows оставались PROVISIONAL во время drain | Немедленная invalidation и отказ поздним callbacks |
| P2 | NaN/Infinity stale thresholds сохраняли ложную freshness | Exact finite positive numeric threshold |
| P2 | Public probe перезаписывал existing output | Early collision refusal; closed+fsync temporary JSON и exclusive hardlink publication; нет output-path echo |
| P2 | PG path/identifier bounds и unbounded operator waits | UNC/invalid Windows components/truncation rejected; trusted connect/query/lock timeouts |
| P2 | Windows trailing separator мог дать false bootstrap refusal | Только separator/trailing normalization с сохранением независимогоID; case/ownership не выводятся из строки |

Для production fixes наблюдались failing targeted cases до исправления и green regressions после. Новые helper/controller safety gates дополнительно проверены fake tests; отдельный -O case не позволяет disposable fixture принять5432. Тесты не соединяются с production. Отдельные development mistakes в тестах/encoding были исправлены до final verification и не выданы за product defects.

Не найдено подтверждённого нового P0 в bounded source review; это не гарантия отсутствия всех дефектов. Win31/Win5 не объявлены ошибкой приложения, PPL/kernel identity или основанием для расширения VERIFIED. Process classifier, service contracts и native collection policy не ослаблены.

## Windows/SCM

Проверены P/Invoke declarations/layout assumptions/error capture/cleanup, QueryFullProcessImageNameW limited rights, PSAPI rights/bounded enumeration, source/lifetime/FILETIME/PID reuse/parent/session/kernel binding, SCM paired membership/types/config/ServiceDll/modules/signature/hash, aggregate co-occurrence/malformed privacy. Все18requested boundaries рассмотрены на source/synthetic уровне. Actual x64 ABI/PPL/VM_READ/physical native snapshots остаются BLOCKED.

Pure Windows PowerShell producer/schema check выполняется только с synthetic providers: 8 positive cases, native methods substituted, collector не dot-sourced. Это не native collector execution. Existing VERIFIED predicates и aggregate-only diagnostics сохранены; диагностический CLI всегда FAIL_CLOSED, authorization NONE, exit1. Нет name-based exceptions, privilege adjustment, защиты PPL не обходятся. Редкие counts не гарантируют анонимность.

## PostgreSQL

PlanOnly по-прежнему выполняет0действий. Physical PGDATA ownership, alias/8.3/junction race resistance и binary provenance не доказываются строковым planner/SQL metadata. Никакого existing5432 connect/use/restart.

G1 script проверяет свежую host/source authorization, encrypted approved path/role, LocalAppData boundary/reparse ancestors, exact18.1 и новый каталог; file control ID получается до server start и передаётся SQL. Никакой автоматический stop/delete по одному пути/флагу больше не разрешён. Failed start мог оставить сервер — только fresh independent ownership/lifetime proof и отдельный manual допуск перед cleanup.

Initializer/preflight/commissioning Store получают независимый ExpectedCluster, проверяют DSN/env и fresh identity до caller SQL; role/db/version/loopback/port/systemID/leastprivilege сохраняются. Transaction-local и session-level path имеют разные lifetime и оба защищены. Normal Store без expectedcluster вне commissioning не становится автоматически аттестованным. Read-only checkpoint ticket не является G1 authorization или durability certificate.

Опциональный новый job `disposable-postgres18`: только GitHub-hosted Linux, после synthetic Windows/Linux, explicit opt-in. Docker tmpfs512MiB/memory768MiB/CPU1/pids128, no host mounts, loopback55480, exact SQL180001. Независимый pg_controldata ID сверяется перед revocations в новом контейнере. Cleanup только exactCID с matching nonce/run/attempt/source labels. Передаются только ephemeral credentials; stdout/private log не публикуются. Четыре real cases проверяют default privileges, initializer/witness SQL, wrong identity/DB/role, READ ONLY и DDL rollback. Здесь Docker/realPG не запускались; default collection skips этих4cases не PASS. Actual SQL/disk durability/server fault recovery BLOCKED до реального job.

## Bybit/Desktop

Сохраняется `TRANSPORT_PASS != DATABASE_PASS != DESKTOP_PASS != FULL_E2E_PASS`. Snapshot/delta/epoch, delta-before-snapshot, regressions, invalidation и fresh recovery проверены fake sockets. Numeric skips depth50 не доказывают packet loss/полную continuity; increasing cross-sequence не считается автоматически +1. UI receive/paint thread contracts проверяются offscreen, не как physical rendering/responsiveness на ADMINIT.

Disk-full/connection-loss в execute/commit проходят через реальный callback boundary с fake transaction; не повышают telemetry/snapshot, вызывают invalidation. Repeated cancellation сохраняет write ownership и исходную ошибку. Cancellation cooperative, hard wall-clock termination не обещан. Thread/task limits не заменяют CPU/RSS/disk measurements; physical budgets требуют свежих реальных samples. Immutable DTO и per-symbol ordering сохраняются.

## CI/provenance/privacy

Новый branch исключён из legacy full/storage jobs. Combined matrix checkout'ит exactPRhead, source receipt, pinned deps, selected source/synthetic suites, complete opaque JUnit identity/status set и exact allowed skips. Dirty tracked source блокирует публикацию даже на failure path. Перед upload обязательны strict projection/validation; raw hostname/SID/PID/DSN/paths/tokens/traceback в payload не допускаются.

Проверены XML/JSON duplicate/malformed/forged identities/counters/statuses/parser and privacy gates. Source-collected set внутри pytest не является независимой криптографической attestation; отдельно сравнивается с source collection. Tripwires — instrumentation reviewed suite, не OS sandbox. HTTP transport guard блокирует unmocked external requests до DNS; reviewed loopback test и MockTransport exceptions ограничены. Arbitrary imports/alternate native APIs/Python children универсально не изолированы.

Исходные mandatory PR47 runs40203571477/40203574132 на read-only API check всё ещё QUEUED, attempt1, exactSHA47, дваjobs каждый, runner_id/group0/emptyname, artifacts0. Причина очереди не установлена. Новый candidate проверяется своими runs; старыеSHA/fixtures не заменяют hosted evidence. ZIP SHA256/manifest/source/run/attempt/job binding проверяется только для фактически доступныхZIP; отсутствиеZIP=BLOCKED. Local SHA256bundle не GitHubZIP digest.

## Test matrix и воспроизведение

Окончательные counts/identities/paths и new-candidate receipt формируются после freeze. Предварительный полный прогон:1731PASS/2expectedsymlinkskips,2liveDPAPIdeselected; после последних controller/provisioning cases count повышается, поэтому этот preliminary count не принимается за final exact-SHA результат. Independent CI/Windows subset387PASS/1platformskip; independent UI/watchdog/probe cross-review51PASS. Pure PowerShell producer8/8PASS отдельно от JUnit. Финальные authoritative counts — в accompanying receipt.

Selected synthetic command находится в `.github/workflows/adminit-final-synthetic.yml`: `python -m pytest --noconftest -p scripts.integration_synthetic_boundary`, QT_QPA_PLATFORM=offscreen, fresh basetemp, liveDPAPI exclusions. `scripts/check_final_integration_junit.py` проверяет полный source-collected set. Новые realPG tests не входят в этот suite и запускаются только controller в отдельном hosted Linux job. Не выполнять controller на ADMINIT и не считатьfake-driver15cases реальнымPG.

## G0–G5 / physical readiness

Подробный [G0 runbook](docs/ADMINIT_G0_SECURITY_RUNBOOK_RU.md): exactsource, host/process/SCM, MetaScalp identity, existingPG isolation/port, filesystem, ExecutionPolicy, environment, CI/privacy, resource budgets и stop conditions. Следующий diagnostic command только подготовлен, никакого autoG0/retry/enrollment. Исторические host facts не считаются свежей attestation.

| Stage | Статус текущей работы |
|---|---|
| G0 | Подготовлен source/runbook; physicalNOT_RUN, mandatoryunresolved и hosted BLOCKED |
| G1 | NO-GO; только после полного G0 и отдельного допуска |
| G2 | NO-GO; реальный publicBybit→DB→Desktop не запускался |
| G3/G4/G5 | NOT_RUN; 30min/2h/24h требуют отдельных PASS/допусков |

Остаточные BLOCKED: actual hosted runs/ZIPs; protected/native/kernel/process identities; real source/host/toolchain/PGDATA ownership; exact server SQL/checkpoint/crash tests; physical API/TLS/GUI/CPU/RAM/disk; длительная стабильность. Synthetic PASS не разрешает commissioning, production service, merge, deployment или trading.

Документированная network projection: [PostgreSQL18 functions-net](https://www.postgresql.org/docs/18/functions-net.html) отличает text(inet) с netmask от host(inet). Source/model regression не заменяет фактический hostedSQLrun.
