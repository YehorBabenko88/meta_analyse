# Один read-only R0–R5 запуск после source review

Адаптер `commissioning/native_scm_diagnostic.py` основан на PR39. Он использует existing collect_facts/assessment, не вызывает assess_processes/classify_missing повторно и не добавляет native API. Восемь host configuration checks выделены из существующего predicate в общую pure функцию; VERIFIED-политика остаётся прежней. Frozen-PR39 differential oracle и legacy regressions ограничивают риск refactor.

## R0 — проверяемый источник и допуск

1. Зафиксировать **final adapter candidate SHA/tree**, source review, actual hosted CI status и решение оператора о ровно одной read-only попытке. Старый SHA39 нельзя передавать как SHA нового адаптера. Никакого автоматического запуска, G1 или enrollment из этого документа.
2. Использовать отдельный чистый Git checkout approved final commit и уже разрешённый Python3.12. Адаптер принимает только exact Git SHA/tree; manifest-only/подписанный modified packet без соответствующего Git tree сейчас не поддерживается. Если signing меняет bytes, нужен новый reviewed commit, а не ослабление binding. Ничего не подписывать/не добавлять в trust/не устанавливать автоматически.
3. Проверить, что существующая PowerShell chain разрешена обычной effective policy. Child `.ps1` файлы не менялись относительно #39. Вызов использует прежний system Windows PowerShell -NoProfile -NonInteractive -File; no Bypass/process override, shell-switch, inline workaround, privilege adjustment или UAC auto-relaunch. При блокировке — STOP.
4. Новый local output должен находиться **вне source checkout**, в уже разрешённом каталоге. Не менять ACL; не использовать существующий output/private observation. Git binding будет отклонять untracked/dirty source. Все файлы evidence держать локально до проверки схемы/privacy; raw facts не сохраняются.

## R1 — ровно одна invocation

После перечисленного source review/операторского допуска, из approved checkout:

```powershell
python -B .\commissioning\native_scm_diagnostic.py --expected-sha <FINAL_SHA> --expected-tree <FINAL_TREE> --output <NEW_LOCAL_JSON_OUTSIDE_CHECKOUT>
$diagnosticExit = $LASTEXITCODE
```

**Exit1 ожидаем всегда.** Это не приглашение повторить запуск с иными правами. Внутри максимум один collect_facts; его child timeout90s сохранён. Source/tree/clean/hash binding проверяется до и в finally после collection, включая error path; changed/unverifiable source полностью удаляет diagnostic summary. Никаких бесконечных retries, фильтрации защищённых процессов или новых probes.

CLI не имеет параметров enrollment/private observation/DSN. Нет save_private, DPAPI, make_policy или startup других программ. При отсутствии elevation/source permission или child failure возвращается только fixed safe refusal. Привилегии не меняются.

## R2 — image diagnostics

Из готовых paired native records публикуются fixed stage/error buckets, alive/lifetime counts и pair stability. Публичных PID/имён/путей нет. Неизвестный stage/error → OTHER, отсутствующая phase → NOT_OBSERVED; malformed types/contradictory source bindings → UNAVAILABLE целиком. Не добавлены GetProcessInformation/IsWow64Process2: protection и architecture имеют NOT_COLLECTED, PPL не угадывается по access denied.

Нулевой creation time допустим только на pre-lifetime failure stage и отмечается NOT_OBSERVED. На шести ранних error stages alive также NOT_OBSERVED: producer default false не доказывает завершения процесса. Поздний NOT_ALIVE отражает только наблюдавшийся producer boolean. Положительный FILETIME проверяется против исходного CIM record; native/kernel/module known times должны совпадать точно. PID reuse, kernel creation drift и parent/session binding mismatch отвергаются. PID0/4 controls сохранены, они не исключаются из inventory.

## R3 — modules

Публикуются phase stage/error counts existing ReadModules, reported complete/incomplete, alive/lifetime и canonical path-set pair stability. REPORTED_COMPLETE не означает VERIFIED. Сохранены QUERY_INFORMATION|VM_READ, bounded enumeration и existing predicates; ALL_ACCESS/SeDebug/PPL обходов нет. Недоступные mandatory modules остаются unresolved; registry/подпись файла не заменяют loaded-module proof.

## R4 — configuration

Для existing reviewed service members публикуются только aggregate PASS/FAIL/NOT_EVALUATED по общим восьми predicate names: member match, registry/SCM type, registry/SCM account, expanded registry host image, registry arguments и SCM arguments. Нет per-service rows/names, accounts, ImagePath/ServiceDll values или hashes. Missing/incomplete config — NOT_EVALUATED, malformed fields — UNAVAILABLE.

Все существующие members сохраняются; первый классификационный отказ берётся из готового assessment. Pair configuration stability отмечается отдельно. DLL source/module/signature/hash поздние predicates адаптер повторно не проверяет и явно помечает NOT_EVALUATED_BY_ADAPTER; PASS восьми config checks не означает прохождения остальных service contracts.

## R5 — прочитать report, остановиться

- Всегда status=FAIL_CLOSED, authorization=NONE, diagnostic_status=READ_ONLY_R0_R5, exit1.
- projection_status=AVAILABLE означает только пригодность aggregate diagnostics. UNAVAILABLE/diagnostics=null — ошибка/недоступность evidence, не ноль отказов.
- reason_counts — process first-refusal units; native/modules — snapshot endpoint units; config — service-member check units. Дополнительные counts не суммируются с process count. Нет per-record joins/pseudonyms/идентификаторов.
- Source должен совпасть с approved final SHA/tree. При error/unknown enum нет raw exception или numeric unknown error reflection. Protection/architecture NOT_COLLECTED не означают unprotected/совпадающую bitness.
- Existing output сохраняется, invocation отказывает до collection. При partial/write/close/stdout error нет PASS/raw fallback; файл может остаться пустым/частичным либо со старым telemetry report. Нужны complete JSON + текущая invocation + schema/source checks, не file existence. Crash durability/interpreter shutdown flushing не доказаны.
- Никаких автоматических повторов/перехода к G1. По результату либо готовится конкретный reproducible synthetic red и узкий fix, либо сохраняется UNKNOWN/UNRESOLVED. Даже0 refusals не даёт authorization.

Public JSON содержит только source code SHA/tree, fixed enums/counters. Raw facts живут лишь в памяти; actual host/process/service identifiers, paths/SID/DSN/hostname/tokens/raw exceptions/file/cert fingerprints не публикуются. Statistical correlation/k-anonymity по агрегатам не гарантируются; default local-only, не автоматический GitHub upload.

В разработке выполнялись только source/synthetic tests. Физический ADMINIT запуск этого адаптера **не выполнялся**. Norton/Defender/ACL/registry/services/PostgreSQL/другие программы не менялись. ADMINIT NO-GO; нет merge/deployment/G1/trading.
