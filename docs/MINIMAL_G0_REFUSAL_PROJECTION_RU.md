# Минимальная проекция отказа G0

Base: точный PR36 e2b3469d4949e7346aaa1709620f1a0c419fcbf4; отдельная ветка и Draft PR. Исходный process_identity.py не меняется. Используются его PUBLIC_PROCESS_REASONS, готовый process_inventory assessment и reason_counts, без нового observer, повторной классификации или нового diagnostic command.

Обычный diagnose при INCOMPLETE_INVENTORY добавляет inventory_refusal. Status/diagnostic_status остаются FAIL_CLOSED, exit1. Snapshot errors до готового assessment дают INVALID snapshot и NOT_EVALUATED/null/empty reason_counts, а не придуманные нулевые результаты. Некорректная проекция даёт только projection_status=INVALID, основной отказ сохраняется.

Публикуются только allowlisted reason_counts и фиксированные состояния process_snapshot, scm_evidence, http_sys_ownership, unknown_process_paths. SERVICE_* определяется из существующего allowlist, а не отдельной таблицей reason codes. Проекция не копирует results, errors, names, PID, пути, hostname/SID/DSN, raw exceptions, fingerprints или host-specific software identifiers. Каждый count должен быть строгим положительным int; assessment/grid counters должны совпадать, sum(reason_counts) должен совпадать с unknown_process_paths. Unknown keys или invalid/contradictory counts не фильтруются молча: проекция отвергается целиком. Сохраняется исходный unknown_process_paths: он включает coverage penalty и не переименовывается в число unresolved identities. Отдельный identity_evidence отличает конкретные identity refusals от coverage-only mismatch; assessment не пересчитывается. Редкий count=1 допустим только для публичного generic reason code, без связи с process record; это не доказательство k-anonymity/отсутствия статистической корреляции.

NO_COVERAGE_REFUSAL и NO_SCM_REFUSAL означают отсутствие соответствующего classifier refusal, а не полноту snapshot/service proof. MATCH_OBSERVED — только текущая HTTP.sys ownership observation; не identity/health authorization. NOT_EVALUATED не означает успех. /ping не заменяет эти доказательства.

Refusal facts становятся доступны проекции только после успешной post-collection source binding. При changed/unverified source дополнительных агрегатов нет. Private save/DPAPI/enrollment при отказе не выполняются; существующие private files не перезаписываются. Protected processes и пять service contracts не исключаются и не ослабляются. Positive diagnose/enroll/check paths не расширены.

## Public output и stale PASS

Сохранён exclusive NewOutput: новый запуск требует нового output пути. Новый refusal записывает только FAIL_CLOSED JSON; write/partial-write/stdout failure не создаёт PASS или private observation. При отказе записи stdout остаётся безопасной ошибкой, exit1. При stdout failure exit1 сохраняется без raw traceback на этом handled boundary.

Существующий output (в том числе со stale PASS bytes или alias private file) **отклоняется, а не перезаписывается/удаляется**. Его bytes могут сохраниться: нельзя безопасно стирать произвольный существующий файл. Они не являются результатом текущего запуска. Consumer обязан проверять exit code/current invocation и использовать новый output; file existence или старые bytes не являются admission. Enroll/check по-прежнему собирают свежие facts и не доверяют public JSON. Crash durability и malicious privileged concurrent writer не доказаны.

## Дочерний PowerShell и ADMINIT policy

Из collect_facts удалён принудительный -ExecutionPolicy Bypass; inherited process-level PSExecutionPolicyPreference удаляется case-insensitively. Остаётся fixed system Windows PowerShell -NoProfile -NonInteractive -File, stdout/stderr capture и timeout. Не изменяются persistent/Group Policy, registry, ACL, AV/firewall; нет inline/shell-switch обхода или auto-sign. Nonzero child даёт fixed COLLECTOR_CHILD_BLOCKED без raw output. Это не устанавливает конкретную причину child failure.

Согласованный с владельцем ADMINIT путь: уже разрешённая действующей policy exact script chain либо утверждённая подписанная цепочка в source/manifest-bound packet. Подпись, trust и policy автоматически не меняются. Если signing меняет bytes, нужны independently trusted manifest digest и полный executable-file coverage; нельзя выдавать изменённый checkout за clean source или ослаблять verify_manifest. Фактическая policy/signature compatibility ADMINIT в этой работе не проверялась и не объявляется согласованной за оператора.

После review/отдельного разрешения на read-only запуск, с новым exact candidate SHA и новым public output, использовать существующий collect-host.ps1/diagnose. PrivateObservation остаётся аргументом прежнего normal command, но при refusal не создаётся. Не запускать raw host-facts.ps1 отдельно и не публиковать его stdout. Python entrypoint также не обходит policy дочернего .ps1. Новых физических запусков здесь нет.

## Проверки

Synthetic tests проходят каждый существующий PUBLIC_PROCESS_REASONS с count1, реальный assess_processes summary без повторного вызова, категории snapshot/identity/SCM/HTTP.sys, malformed/unknown/contradictory counters, ошибки collection/binding/public write/stdout и stale/existing files. Raw local JUnit остаётся приватным; CI публикует только minimal staged JUnit с exact source/tree/run/attempt/job binding.

Branch выполняет только dedicated Windows/Linux synthetic и существующий kernel offline workflow. Full/native/storage jobs исключены; PG audit/** trigger не совпадает с parallel branch. Их SKIPPED/NOT_RUN не являются PASS. ADMINIT failure причина пока UNKNOWN; новая проекция должна помочь после отдельно разрешённого запуска, а не разрешить G1.

**ADMINIT NO-GO. Нет merge, G1, cluster creation, deployment или торговых операций.**
