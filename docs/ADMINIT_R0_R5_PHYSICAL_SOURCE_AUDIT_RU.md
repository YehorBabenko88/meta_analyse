# Физический результат R0–R5 PR40: source-аудит 2026-10-25

## Scope и вывод

Аудируемый exact PR40 HEAD: `16f5299e1b83bb4e527563e39fd889a4f90aaffa`. Физические результаты взяты только из сообщения оператора; raw observation не запрашивалась, ADMINIT не запускался. Повторная native collection, повышение привилегий и изменения системы не выполнялись.

Подтверждён **P2 diagnostic correctness**: при раннем native/module failure default `alive=false` отображался как NOT_ALIVE. Это не admission bypass: G0 оставался FAIL_CLOSED, authorization NONE, exit1. Исправление меняет только diagnostic projection на NOT_OBSERVED для шести существующих early stages. Producer и classifier не меняются.

## Registry/SCM type и пять contracts

`service_host_configuration_checks()` требует точный Python int32 (`0x20`) независимо в Registry и SCM для всех пяти reviewed contracts:

| Contract | Host | DLL/source | Args/account | Type policy |
|---|---|---|---|---|
| KeyIso | lsass.exe | keyiso.dll / parameters | no args / LocalSystem | exact32 / exact32 |
| SamSs | lsass.exe | samsrv.dll / integrated, ServiceDll absent | no args / LocalSystem | exact32 / exact32 |
| VaultSvc | lsass.exe | vaultsvc.dll / parameters | no args / LocalSystem | exact32 / exact32 |
| DoSvc | svchost.exe | dosvc.dll / root | -k NetworkService -p / NetworkService | exact32 / exact32 |
| wscsvc | svchost.exe | wscsvc.dll / parameters | -k LocalServiceNetworkRestricted -p / LocalService | exact32 / exact32 |

Эта таблица описывает **текущую reviewed policy исходников**, а не универсальное утверждение обо всех Windows builds. File image, paired configuration, membership, raw/expanded arguments, modules, lifetime, signature/hash и DLL source по-прежнему обязательны. Для SamSs отсутствие ServiceDll не отменяет independent samsrv.dll module/signature proof.

Microsoft различает SERVICE_WIN32_OWN_PROCESS=0x10 и SHARE_PROCESS=0x20; INTERACTIVE_PROCESS=0x100 — дополнительный флаг при определённых условиях, не взаимозаменяемость типов. Windows-valid type16 или0x120 не означает reviewed contract. Нельзя заменить exact32 на mask/nonzero/16-or32 без independent Windows-build/contract evidence. `32.0` и `True` также не exact integer32.

[QUERY_SERVICE_CONFIGW — Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-query_service_configw)

**Связь двух FAIL с одним контрактом не установлена.** Marginal counts Registry FAIL1 и SCM FAIL1 совместимы как с одним member с двумя отказами, так и с двумя members по одному. Synthetic counterexample воспроизводит одинаковые totals по пяти contracts для обеих схем. Две одинаковые фазы не добавляют per-member join. Другие шесть checks PASS5 показывают пять evaluated member checks в каждой фазе, не имена или точные типы. Реального classifier defect из этих агрегатов не доказано; policy не расширена.

Если потребуется следующий диагностический этап, достаточно отдельно reviewed фиксированного aggregate co-occurrence (both/registry-only/scm-only) и allowlisted raw-type categories с privacy review. В этом минимальном исправлении новая телеметрия не добавляется и физический rerun не предлагается автоматически.

## QUERY_IMAGE / Win32 31

Source использует explicit QueryFullProcessImageNameW, Unicode/SetLastError, PROCESS_QUERY_LIMITED_INFORMATION=0x1000, flags0 и buffer32768 characters. GetLastWin32Error считывается сразу после false. Отдельная flags1 попытка при error31 не заменяет flags0 path или исходный код ошибки.

По Microsoft error31 — ERROR_GEN_FAILURE, общий код ошибки, а не свидетельство kernel identity, PPL, отсутствия файла или конкретной ошибки ABI. flags0 означает Win32 path, flags1 — native path. MATCНED lifetime и paired MATCH подтверждают только согласованность имеющихся snapshot fields; successful image identity из ошибки не возникает. Kernel evidence для PID вне0/4 тоже не создаёт исключение. Проверки native-format success/false сохраняют IMAGE_PATH_UNAVAILABLE, без raw path projection.

[QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew), [Win32 error codes](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--0-499-).

Нового доказанного дефекта вызова/обработки error31 не найдено source/synthetic средствами. Root cause на конкретном ADMINIT остаётся UNKNOWN; PPL/architecture NOT_COLLECTED нельзя интерпретировать как отрицательный результат.

## OPEN_PROCESS_MODULES / Win32 5

ReadModules запрашивает QUERY_INFORMATION|VM_READ (0x0410). OPEN_PROCESS_MODULES означает, что OpenProcess не вернул handle: EnumProcessModulesEx ещё не вызывался. Win325 = ACCESS_DENIED; конкретная причина (DACL/token/protection) из кода не определяется. Microsoft описывает ограничения этих прав для protected processes; это совместимо с ограничением доступа, но не доказывает PPL конкретного process. Никаких SeDebug, ALL_ACCESS, ACL/protection изменений, retries с повышением прав или обходов не добавлено.

[Process access rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights), [EnumProcessModulesEx](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-enumprocessmodulesex).

Registry/SCM/file signature не заменяют loaded-module proof. Если обязательные modules недоступны при разрешённых правах, соответствующий admission остаётся UNRESOLVED. Три module endpoint failures и два SERVICE_MODULES_UNAVAILABLE process first-refusals не противоречат source: module collection выполняется для нескольких candidates, а classifier возвращает первый отказ; config/rule refusal может предшествовать modules. Без joins нельзя назначить endpoint конкретному отказу.

SERVICE_RULE_UNREVIEWED — отдельный отказ отсутствия reviewed service rule; его service identity из counters неизвестна. Name-based исключение или автоматическое обучение правила по observation не допускается.

## P2 и red/green

C# ProcessRow/ModuleSet bool defaults false. OPEN_PROCESS/GET_PROCESS_TIMES/GET_EXIT_CODE и OPEN_PROCESS_MODULES/MODULE_PROCESS_TIMES/MODULE_EXIT_CODE возвращаются до присвоения `created` и `alive`. Поэтому defaultfalse не является observation о смерти. Fix: для этих stages alive_counts=NOT_OBSERVED. На более поздних QUERY_IMAGE/ENUM_MODULES/MODULE_PATH stages bool уже присвоен, ALIVE/NOT_ALIVE сохраняются. Даже observed NOT_ALIVE — результат producer boolean на snapshot, не причина завершения и не authorization.

Новые45 synthetic cases: 6 early-stage regressions (RED6FAIL), 6 post-liveness controls, 30 exact-type policy controls для пяти contracts, 1 aggregate-correlation counterexample, 2 error31 native-format controls. До исправления 6FAIL/39PASS; после исправления targeted suite315cases:314PASS/1symlink capability skip. Первый общий green запуск упёрся в pytest temp-junction cleanup PermissionError вне product code; повтор в новом изолированном synthetic basetemp завершился exit0. Никакие ACL/temp system objects не менялись.

Source re-review независимым reviewer подтвердил соответствие producer/fix и не нашёл P0/P1/P2 в delta. Его PATH Python не имел pytest, поэтому independent runtime PASS не заявляется. Тесты основного агента используют существующий отдельный Python3.12 venv.

## Матрица приёмки

| Граница | Вердикт |
|---|---|
| Неверная early-failure alive projection | P2 доказан, исправлен red/green |
| Связь Registry/SCM FAIL с одним контрактом | UNKNOWN, counterexample доказывает недостаточность totals |
| Новый classifier admission defect | Не доказан; policy/VERIFIED не изменены |
| Error31 превращается в path/kernel identity | Synthetic PASS: остаётся UNRESOLVED |
| Module access denied | Runtime причина UNKNOWN; mandatory proof BLOCKED |
| Privacy / no authorization | Existing fail-closed/privacy synthetic controls сохранены |
| Physical root cause/PPL/native ABI | BLOCKED, не тестировались |
| G0 | FAIL_CLOSED по сообщению оператора |
| G1/commissioning | NO-GO |

Exact SHA/tree нового Draft PR и fresh local/hosted результаты фиксируются в accompanying audit report после commit; прежние SHA не используются как доказательство нового CI. Никаких merge, deployment, торговых операций, PostgreSQL или системных изменений.
