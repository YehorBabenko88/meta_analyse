# G0: aggregate-only причины отказа

База: неизменённый PR36 `e2b3469d4949e7346aaa1709620f1a0c419fcbf4`. Отдельный кандидат добавляет режим объяснения отказа; он не исправляет неизвестную причину фактического ADMINIT отказа и не разрешает G1.

## Контракт

Новая команда `host_identity.py diagnose-aggregate` / switch `collect-host.ps1 -AggregateReasons` не принимает private observation/enrollment path. Она всегда выдаёт JSON `status=FAIL_CLOSED`, `diagnostic_status=AGGREGATE_ONLY_NOT_AUTHORIZATION`, `authorization=NONE`, exit1, даже если все доступные observations выглядят полными. Exit1 в этом режиме ожидаем и не означает, что JSON не удалось сформировать.

Один JSON печатается в stdout и записывается в **новый** output file (существующий файл не перезаписывается). При отказе записи stdout сообщает fixed failure; файл может быть пустым/частичным reservation. Это не crash-durable transaction, не enrollment input и не successful admission receipt. Использовать stdout/exit и schema вместе; наличие файла само по себе не PASS. Отмена/ошибка режима также не создаёт authorization.

Public output содержит только фиксированные ключи/значения и агрегированные integer counts или null. Нет PID, process/service/queue names, paths, SID, DSN, hostname, fingerprints, tokens, raw exception text, per-process lists или dynamic reason keys. Raw facts остаются только в памяти capturing Python process; `save_private`, DPAPI, target enrollment и admission не вызываются.

| Поле aggregate | Смысл / ограничения |
|---|---|
| snapshot_status / inventory_error_count | Тип/coverage исходного списка и общее число collector errors; raw messages не копируются |
| source_snapshot_status | Дошёл ли pipeline до существующей CIM/evidence snapshot binding validation; VALIDATED не доказывает native trust |
| process_status / unresolved_count | Результат существующего classifier aggregate; protected processes не исключаются, mismatch также учитывается |
| scm_status / incomplete_scm_snapshots | Заявленные collector flags before/after; COMPLETE означает только наличие complete flags, не самостоятельную service authorization |
| incomplete_module_snapshots | Число отсутствующих/неполных запрошенных module groups |
| scm_refusal_count / module_refusal_count | Суммы фиксированных service/module категорий из classifier refusals; без исходных reason keys/имён |
| http_sys_status | Удалось ли существующему parser сопоставить queue owner с terminal record; MATCHED_OBSERVATION_ONLY не доказывает identity, software version или API health |

Стадии, не достигнутые после malformed snapshot/schema/child failure, остаются NOT_EVALUATED/null. Это **не ноль ошибок**. SCM/type/schema ошибки могут блокировать классификацию до появления unresolved_count; в этом случае нельзя утверждать, что все процессы проверены. После source change агрегаты отбрасываются. HTTP.sys неизвестный/localized format остаётся unresolved; `/ping` не заменяет queue ownership proof. Enroll/check и все existing predicates остаются отдельными fail-closed путями.

## Policy-compliant дочерний collector

`collect_facts()` больше не задаёт `-ExecutionPolicy Bypass` и удаляет inherited process-level `PSExecutionPolicyPreference` case-insensitively. Используется тот же system Windows PowerShell с `-NoProfile -NonInteractive -File` и ограниченным Windows module path. Не меняются persistent execution policy, Group Policy, registry, ACL, AV/firewall; нет inline script обхода, смены shell или auto-sign.

Если child завершается nonzero, возвращается фиксированный `COLLECTOR_CHILD_BLOCKED`, а stderr/stdout child не публикуются. Этот код **не устанавливает**, вызван ли отказ policy, native API, подписью или другой runtime ошибкой. Нельзя разбирать raw exception text ради автоматического обхода.

Рабочий способ запуска требует согласованной с владельцем ADMINIT политики: либо exact scripts уже разрешены действующей policy, либо оператор предоставляет разрешённую подписанную цепочку wrapper → host-facts → process-evidence в проверенном source packet. Подписание/добавление доверия не выполняются автоматически. Если Authenticode меняет source bytes, обычный clean Git binding уже не соответствует checkout: нужен отдельно проверенный manifest-bound packet с exact candidate SHA и доверенным SHA256 manifest, включающий все executable scripts. Нельзя редактировать/переподписывать исходники после attestation или ослаблять verify_manifest ради запуска. Этот PR не подтверждает допустимость конкретной подписи или policy ADMINIT.

## Только после отдельного разрешения на read-only запуск

На approved exact checkout, из уже разрешённой Python3.12 среды (без нового install/venv), предпочтительный прямой entrypoint:

```powershell
python -B .\commissioning\host_identity.py diagnose-aggregate --expected-sha <EXACT_NEW_CANDIDATE_SHA> --output <NEW_LOCAL_AGGREGATE_JSON>
```

Python entrypoint не обходит child PowerShell policy: дочерний `.ps1` по-прежнему обязан быть разрешён обычной effective policy. Не передавать SHA старого PR36 как SHA нового кандидата. Для approved packet дополнительно задать `--manifest <APPROVED_MANIFEST> --manifest-sha256 <TRUSTED_DIGEST>`. Оба параметра требуются совместно.

Если wrapper разрешён действующей policy:

```powershell
.\commissioning\collect-host.ps1 -AggregateReasons -ExpectedSha <EXACT_NEW_CANDIDATE_SHA> -Output <NEW_LOCAL_AGGREGATE_JSON>
```

В новом parameter set нет PrivateObservation. Не добавлять `-ExecutionPolicy Bypass`; не перенаправлять raw `host-facts.ps1`/native output в публичный файл. Summary не включать в CI автоматически и не считать сигналом G1. Повторный physical collector в этой разработке **не выполнялся**.

## Synthetic CI и воспроизведение

Dedicated workflow `G0 aggregate diagnostics synthetic` использует Windows/Ubuntu, Python3.12, pinned pytest и `--noconftest`; все host calls подменены synthetic fixtures/tripwires. Exact source/tree receipt и minimal JUnit публикуются через существующий staged privacy publisher. Никаких real collector, live DPAPI, PostgreSQL или host inventory в этом workflow. Main/native/storage jobs исключают эту конкретную branch; PG push filter audit/** не совпадает с parallel/... . Skipped incompatible jobs не объявляются PASS.

```powershell
python -B -m pytest --noconftest tests/test_g0_aggregate_diagnostics.py tests/test_public_junit.py tests/test_project_public_ci_evidence.py tests/test_public_evidence_workflows.py -q
```

Покрываются malformed outer records, None/bool/float/unhashable PID, duplicate/missing/changing snapshots, SCM/modules, HTTP.sys, source mismatch, elevation, child failure/timeout, output collision, invalid CLI/private sentinel leakage и wrapper contract. Existing classifier/host regressions запускаются отдельно в synthetic-only среде, с явным исключением двух real-DPAPI tests. PowerShell AST parse не исполняет collector.

**ADMINIT NO-GO. G0 остаётся BLOCKED до отдельной фактической приёмки. Нет G1, cluster creation, deployment, merge или торговых операций.**
