# ADMINIT: полный read-only G0 runbook нового кандидата

## Запрет автоматического выполнения

Этот документ — инструкция для отдельного решения оператора, а не разрешение на запуск. В текущей работе физический G0 не выполняется. G1–G5, создание кластера, любые DDL/DML на ADMINIT, изменение5432/Windows/Norton/Defender/ACL/служб/реестра/Grid и торговые операции запрещены. До завершения source review и актуальной hosted acceptance статус G0 preparation=BLOCKED.

Exact новый SHA/tree оператор берёт из итогового acceptance receipt и GitHub Draft PR. PR47 `59626930a911c0dde330f7760c78ccd99468a1f4` — только база, не SHA нового кандидата. Любое исправление, подпись, перенос файла или нормализация packet вне reviewed tree требует повторного source binding/review; старый PASS не переносится.

## Предварительные обязательные gates

1. Проверить HEAD/tree/base/merge-base и clean source. SHA/tree должны совпадать с новым receipt и фактическим checkout; `git status --porcelain` должен быть пуст. Runtime/output/venv размещаются вне checkout. Не доверять одному имени ветки или stale JSON.
2. Получить реальные new-candidate Windows/Linux runs, attempts/jobs/runner assignment, полный JUnit identity/status set и public artifact manifests/ZIP SHA256. QUEUED/SKIPPED/отсутствие artifacts не PASS. Разрешённые capability skips не становятся доказательством соответствующей filesystem capability.
3. Отдельно проверить disposable Linux PG18.1 job. Это server SQL proof для одноразового контейнера, не доказательство ADMINIT PostgreSQL или physicalG1. При pending/failure — STOP и source remediation.
4. Оператор явно допускает ровно одну физическую read-only попытку, фиксируя exact SHA/tree и разрешённый способ исполнения. Не переходить между этапами автоматически.

## Чеклист G0 до invocation

Все реальные значения остаются в утверждённом локальном evidence месте; в чат/Actions/public artifacts передаются только reviewed fixed enums/counters. Не просить и не публиковать hostname/SID/PID/process/service names/paths/DSN/password/token/raw exceptions. Исторические сведения об ADMINIT не считаются свежей проверкой.

| Граница | Что требуется установить | STOP condition |
|---|---|---|
| Source | Exact commit/tree, approved clean checkout, running root/collector identity, before/finally binding | Любое расхождение/dirty/неверифицируемый источник |
| Host | Windows11Pro, нужный user/elevation/identity в private policy; отсутствие запрещённых footprints | Unknown identity/elevation/coverage/Grid evidence |
| Python/PowerShell | Approved Python3.12, поддерживаемая bitness, WindowsPowerShell5.1; проверенные package/tool hashes | Непроверенный interpreter/toolchain, несовместимая architecture |
| ExecutionPolicy | Свежая effective policy всех relevant scopes; разрешение на текущие scripts/child chain | Не менять policy, не использовать Bypass/inline/base64/shell-switch/auto-elevation/Unblock-File для обхода |
| Native/SCM | Полный snapshot, paired membership/lifetime, independent identities, строгие types/config/modules/hash/signature | Любой mandatory unresolved. Win31 не kernel/PPL proof, Win5 не объясняет конкретную причину |
| MetaScalp | Fresh process/API identity, approved binary hash/signature/version/endpoint/PID lifetime privately | Missing/mismatch/API-only ping без identity недостаточен |
| Existing PostgreSQL | Только OS/service/listener metadata для изоляции existing5432/PGDATA boundaries | Не подключаться к5432, не читать его таблицы, не перезапускать и не использовать для теста |
| New target | 127.0.0.1:55480 свежо свободен; будущий PGDATA не пересекается с existingdata | Порт занят/unknown, path overlap/reparse/alias/collision |
| Filesystem | Новый local output вне source/venv/existingprivate; проверенные ancestors и разрешённый каталог | Existing output/private alias; не перезаписывать, не менятьACL |
| Environment | Отметить наличие PG*/DSN/proxy/CA overrides без раскрытия значений | Не использовать production DSN, не очищать глобальный env и credentials автоматически |
| Resources | Свежие CPU/RAM/disk/queue baseline и утверждённые budgets | Unknown measurements, недостаточный ресурс, превышение stop budgets |
| CI/privacy | Exact new candidate evidence и reviewed aggregate schema | СтарыйSHA/ложныйPASS/непрозрачныйartifact/private payload |

Проверка metadata существующего PostgreSQL не является SQL-соединением. PostgreSQL binaries перед будущим G1 требуют независимой проверки происхождения/hash/signature; один вывод --version этого не доказывает. Не запускать initdb/pg_ctl/psql на ADMINIT в G0.

## Ровно одна diagnostic invocation после отдельного допуска

Из approved checkout, существующим approved interpreter, с новым output:

```powershell
python -B .\commissioning\native_scm_diagnostic.py --expected-sha <NEW_EXACT_SHA> --expected-tree <NEW_EXACT_TREE> --output <NEW_APPROVED_LOCAL_JSON_OUTSIDE_CHECKOUT>
$diagnosticExit = $LASTEXITCODE
```

Ожидаются FAIL_CLOSED, authorization NONE и exit1 всегда. Projection AVAILABLE означает только пригодность aggregate diagnostics. Никаких enrollment/private authorization, G1 или следующего collector invocation автоматически.

Native collector использует существующую reviewed цепочку. Она не запускается этим документом; если effective policy/защита Windows не допускают её, STOP без изменений защиты/прав. Raw facts остаются в памяти existing collector/adapter. При отказе private authorization не создаётся.

Проверить complete JSON/current invocation/source SHA/tree; не считать file existence доказательством. Передать только разрешённую aggregate projection. `configuration.before/after.type_cooccurrence`: BOTH_FAILED/REGISTRY_ONLY_FAILED/SCM_ONLY_FAILED/NEITHER_FAILED/NOT_EVALUATED, без per-member joins. Не складывать две фазы как разные службы. NEITHER_FAILED касается лишь двух type predicates, а не service admission.

Любой malformed evidence/source/lifetime mismatch → UNAVAILABLE, не partial PASS. Редкие counts могут коррелировать с внешними данными; анонимность не гарантируется, default local-only. Если обязательные predicates unresolved, G0 остаётся FAIL_CLOSED и G1 NO-GO, даже если остальные проверки прошли.

## Stop, evidence и recovery

- Одна попытка; без retry, privilege adjustment, name exceptions и изменений Windows.
- Сохранить только approved local JSON/операторский чеклист и source/CI receipts. Raw stderr/private observations не публиковать.
- Закрыть только собственный diagnostic process нормальным способом; не останавливать чужие процессы/службы.
- При partial output или failed publication не использовать его как подтверждение и не перезаписывать существующий файл следующей попыткой.
- В G0 нет созданного кластера или deployment, поэтому rollback не должен затрагивать PGDATA/5432/программы.
- При будущем отдельно разрешённом G1 failure новый PGDATA сохраняется для review. Автоматический pg_ctl stop удалён: path/$started не доказывают владельца процесса. Даже failed start мог оставить сервер. Перед любым stop/cleanup нужны свежие system_identifier, exact physical PGDATA ownership, process/lifetime/executable/listener и отдельное решение оператора. Если proof отсутствует — сохранить BLOCKED, ничего не удалять.

## G1–G5

Для каждого этапа — отдельный source-matched PASS и отдельный допуск, собственный log/evidence scope, budgets, stop conditions и rollback ownership. Pure stage_acceptance.py оценивает только поданные поля и не аутентифицирует receipts; его PASS не даёт authorization и не начинает следующий этап.

G1: изолированная установка/кластер/least privilege/migrations/rollback. G2: publicBybit→committedDB→readback/checkpoint→Desktop, с разделёнными TRANSPORT_PASS/DATABASE_PASS/DESKTOP_PASS/FULL_E2E_PASS. G3=30min, G4=2h, G5=24h. Ничего из этого в текущей работе не выполняется на ADMINIT. Physical crash durability, PPL/module access и длительная responsiveness требуют собственных реальных доказательств.
