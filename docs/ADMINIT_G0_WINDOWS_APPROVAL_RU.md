# ADMINIT_G0_WINDOWS_APPROVAL_RU — независимая оценка, 2026-10-26

## Решение
**Безусловное разрешение физического G0 НЕ ВЫДАНО.** Один новый read-only G0 допустим только после отдельного подтверждения оператором перечисленных ниже условий. G1, deployment и изменение Windows security запрещены. Этот аудит выполнен через GitHub; ADMINIT физически не запускался.

## Exact source / evidence
PR #52 HEAD `8a1c20184cbd878097f62530fc07630568fb7f84`, tree `334df27319ce37fe562b6195b255742dae6db8c8`, base/merge-base `b595a3a88d32eb6e93c94bbe5d26abeacb4712de`. С PR #43 (`a04f132d64db0981ef93de1be8208612de08a194`) совпадают Git blob SHA:
- `commissioning/process-evidence.ps1`: `57ebcec365a929557a7f7d93c9f9b3c1a965a8be`
- `commissioning/process_identity.py`: `69b1b5793aa2992017369a8309863c94c41f47cd`
- `commissioning/native_scm_diagnostic.py`: `223d283b7cc9c6ae1e882049790f776287d5f95d`
- `commissioning/host-facts.ps1`: `3fd04a385987d2fa9343e7a24e523f35d5867f21`

Exact PR #52 hosted synthetic push run 40295973256 и PR run 40295979565: по API каждый имеет 3 завершённых SUCCESS jobs (Windows, Linux, disposable PG18) и 3 неистёкших artifacts. Это metadata/CI success, **не** самостоятельная побайтовая перепроверка содержимого ZIP в этом аудите. Автор PR сообщает 1744 PASS для Windows/Linux и 4 PASS для disposable PG на каждом run, но эти числа не были независимо восстановлены из JUnit здесь. CI/storage workflows, отмеченные SKIPPED, не считаются PASS.

## Исторический физический G0
PR40: семь UNRESOLVED assessments, QUERY_IMAGE Win32 31 ×3 first-refusal, OPEN_PROCESS_MODULES Win32 5 ×3 endpoint в каждой фазе, REGISTRY_TYPE_REVIEWED FAIL1, SCM_TYPE_REVIEWED FAIL1, SERVICE_RULE_UNREVIEWED1, HTTP.sys ownership MATCH_OBSERVED, G0 FAIL_CLOSED. Эти данные нельзя считать повторным физическим тестом PR52. Error31 не доказывает PPL; ACCESS_DENIED 5 не доказывает ни PPL, ни отсутствие модулей.

## Windows/SCM integrity
Reviewed contracts: KeyIso, SamSs, VaultSvc, DoSvc, wscsvc. Registry и SCM требуют отдельно `type(x) is int and x == 32` (не mask, не bool/float/16/0x120). Service membership оценивается per-member даже при одном PID shared host. Пять co-occurrence buckets: BOTH_FAILED, REGISTRY_ONLY_FAILED, SCM_ONLY_FAILED, NEITHER_FAILED, NOT_EVALUATED. Неопределённое/неполное evidence не превращается в NEITHER_FAILED. Агрегаты не дают права VERIFIED; прежние classifier/producer bytes сохранены.

Source/lifetime: требуются точный SHA/tree и collector identity до/после, clean checkout, PID+creation FILETIME, kernel parent/session, стабильные native/module snapshots, SCM/Registry/ServiceDll, mapped modules, Authenticode и SHA256. Source binding и снимки снижают риск PID reuse, но не устраняют произвольную подмену между измерениями. Нельзя объявлять защищённый процесс VERIFIED по ошибке доступа или только по имени.

## Матрица
| Gate | Result |
| --- | --- |
| Exact PR52 HEAD/tree | PASS |
| Four Windows producer/classifier blob SHA equal PR43 | PASS |
| Co-occurrence strict reviewed policy | PASS source-only; independent physical BLOCKED |
| Hosted Windows/Linux/disposable PG jobs | PASS as GitHub job conclusions |
| Independent ZIP/JUnit SHA256 content verification in this audit | NOT_RUN |
| Physical ADMINIT PR52 G0 | NOT_RUN |
| Historical seven unresolved | FAIL_CLOSED, not waived |
| PPL / Win3231 / Win325 root cause | BLOCKED |
| G1 | NO-GO |

## Что можно передать в чат
Предпочтительно только `status=FAIL_CLOSED`, число unresolved с широкими интервалами (например, `1–9`, `10+`), фиксированные публичные reason categories и факт `NOT_COLLECTED`/наличия ошибок без редких точных joins. Даже точные редкие counts 1, 2, 3, per-phase co-occurrence, сочетания категорий и последовательности запусков могут позволить восстановить service identity по внешнему знанию. **По умолчанию не публиковать** raw JSON, PID, process/service names, exact type values, paths, hostnames, usernames, SID, hashes, certificates, ports, DSN, timestamps, per-member correlation или архивы. Точные totals и bucket counts передавать только после отдельной privacy-проверки; округление/интервалы не гарантируют анонимности.

## Условия одного нового read-only G0
1. Оператор отдельно подтверждает физический хост ADMINIT, окно, scope, права на сбор, private output path и отсутствие запуска G1. Зафиксировать approved SHA/tree PR52 и clean worktree, проверенный подписанный/разрешённый PowerShell execution path; **не применять ExecutionPolicy Bypass**.
2. Проверить без изменений системы Windows 11 x64, Python 3.12, PowerShell, privilege token и версии native collector. Не отключать Defender/Norton, не изменять ACL, SCM, registry, firewall, процессы и PostgreSQL.
3. До запуска подтвердить, что read-only native probes разрешены оператором и не требуют обхода PPL, SeDebugPrivilege или VM_READ retry с повышением прав. Сырые данные сохранять только приватно с ограниченным доступом.
4. Собрать только один bounded R0–R5, проверить before/after source binding, lifetime и SCM membership. Не исключать LSASS/svchost из inventory и не повышать UNRESOLVED в VERIFIED по имени.
5. После запуска проверить локально exit/status, sanitized report и отсутствие секретов; отдельная независимая приёмка обязательна до любого нового шага.

## Mandatory STOP
- Wrong SHA/tree, dirty worktree, неизвестный/неутверждённый collector или изменившийся источник между снимками.
- Неверный хост/учётная запись, unexpected elevation, ExecutionPolicy bypass, необходимость менять защиту/ACL/службы или обходить PPL.
- PID reuse, FILETIME mismatch, parent/session mismatch, snapshot drift, incomplete SCM, ServiceDll ambiguity, module list inconsistency, подпись/хэш mismatch.
- Win32 31/5 на обязательном proof path, неполный module evidence, SERVICE_RULE_UNREVIEWED или любое unknown evidence — **STOP для VERIFIED/G1**, не попытка получить PASS обходом.
- Непредусмотренная запись, утечка raw данных, непроверенный public artifact, нарушение лимита ресурсов или cleanup failure.
- Любое unexpected PASS/VERIFIED при отсутствии обязательных доказательств — security incident и STOP.

## P0/P1/P2
P0 подтверждённых новых обходов не выявлено на уровне source/blob сравнения. P1: физический PR52 G0 не выполнен; hosted ZIP/JUnit content не перепроверен этим аудитом; редкие агрегаты требуют privacy acceptance. P2: root cause Win3231/5 неизвестен; остаточный TOCTOU и source/runtime environment binding требуют физической оценки. **Final: G0 conditional operator-only; G1 NO-GO.**

## Независимая повторная проверка CI (2026-10-26)
На exact PR53 HEAD `047174046a5d9d32fa1b3dc4038cb34dc1845db3` workflow CI run 40300503050 при проверке имел Linux job IN_PROGRESS, Windows и archive-pinned-contract QUEUED. Это не PASS и не новая физическая приёмка. Изменение документа после этой проверки требует нового exact-head CI; исторические run conclusions не переносятся.
