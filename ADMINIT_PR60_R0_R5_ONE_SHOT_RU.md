# ADMINIT PR60 — одна отдельная R0–R5 попытка

**PREPARED / NOT_RUN.** Target HEAD `0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30`,
tree `a85846d46df6e95f3d757e25399d991ee1db872b`.

Это самостоятельное решение оператора после положительного **подлинного**
preflight; не следующий автоматический шаг format-only runbook. Если в текущей
session уже выполнен format probe — STOP: R0 требует нового scope/record review
и отдельного явного допуска. Ни source/CI PASS, ни READY_FOR_OPERATOR_REVIEW JSON
не заменяют согласие и independent host provenance.

## Mandatory preconditions

Все строки `ADMINIT_PR60_G0_PREFLIGHT_RU.md` для mode R0_R5 удовлетворены свежими
private authenticated evidence: host/user/elevation, independent tool/DLL/loaders,
exact target source/clean namespace, policy/MOTW, approved existing Add-Type/C#
compiler/temp chain, output/writer/resources, PG5432 isolation и operator scope.

Не требовать VERIFIED process identities до диагностической попытки — они её цель;
но известный unsafe execution/toolchain/namespace или Grid conflict блокирует
сам запуск. Исторические Win31/Win5/unresolved результаты не новые observations.

R0 source вызывает Windows native APIs через существующий Add-Type collector.
Никакого второго native test/ABI smoke/PPL bypass/SeDebugPrivilege/VM_READ retry с
повышением прав. Не выполнять `check-process-probe.ps1`, diagnose/enrollment,
collect-host.ps1, PostgreSQL preflight.py, installer, G1–G5 или UI/Bybit E2E.

## Ровно один вызов, только оператором

`$g0Repo/$g0Python/$r0Output` — approved absolute private paths. `$r0Output`
никогда не preflight/format/private-authorization path и не reused leaf.

```powershell
$r0Stdout = @(& $g0Python -B -E -s -S (Join-Path $g0Repo 'commissioning/native_scm_diagnostic.py') --expected-sha 0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30 --expected-tree a85846d46df6e95f3d757e25399d991ee1db872b --output $r0Output 2>$null)
$r0Exit = $LASTEXITCODE
# STOP после одного invocation: exit1 ожидается; никаких retry/format/enrollment/G1.
```

Не выполнялось в этой работе. Internal host-facts.ps1/process-evidence.ps1 не
вызывать отдельно, не dot-source collector интерактивно и не сохранять raw stream.
Python child capture остаётся private/in-memory; дочерний Windows PowerShell
получает -NoProfile/-NonInteractive/-File и системный PSModulePath, без Bypass.
PSExecutionPolicyPreference не наследуется; preflight тем не менее блокирует
неизвестный/присутствующий override, а не «исправляет» его удалением глобально.

## Приёмка одного результата

Exit **1**, schema1, status **FAIL_CLOSED**, authorization **NONE**,
diagnostic_status READ_ONLY_R0_R5. AVAILABLE означает лишь полную диагностическую
projection существующих assessments. Проверить полный новый output + captured
stdout + exit + source pair и current session; не доверять одному file existence.
Malformed/missing/partial, output/close failure или source drift → BLOCKED/STOP.
Никакой private authorization при отказе не сохраняется.

| Область | Разрешённое evidence | Отказ |
|---|---|---|
| R0 source | SHA/tree/collector bytes до/после | mismatch/dirty/unreviewed loader → STOP |
| Snapshot/lifetime | Уже полученные CIM/native pairs, PID+creation binding внутри private boundary | missing/malformed/PID reuse/drift → UNAVAILABLE/FAIL_CLOSED |
| Image/native | Aggregate error_stage/Win32 categories из существующего assessment | QUERY_IMAGE31 не PPL/kernel proof и не name exception |
| Modules | Aggregate enum phase/lifetime/alive categories | ACCESS_DENIED5 не отсутствие DLL и не завершение; early-open alive default не observation |
| SCM/config | Five reviewed contracts, complete before/after membership/config | Registry/SCM BOTH/ONLY/NEITHER/NOT_EVALUATED не раскрывает имён и не VERIFIED promotion |
| HTTP.sys | Строгий supported grammar + unique ownership/lifetime в прежнем classifier | unknown/localized/ambiguous или /ping/port alone → UNRESOLVED |
| Host/PG/G1 | Никаких новых правил authorization | Любой mandatory unresolved: G0 FAIL_CLOSED, G1 NO-GO |

Protection/architecture NOT_COLLECTED не интерпретировать как подтверждение.
Не ослаблять image/signature/hash/ServiceDll/mapped-module/service type contracts
ради прохождения inventory. Никаких исключений для имён Windows processes.

## Privacy, остановка, остаточные ограничения

Не публиковать PID, process/service names, Windows service types, пути, usernames,
SID, hostname, DSN/tokens, native raw error text или raw HTTP.sys. `$r0Stdout`
держать private до проверки фиксированной schema. Даже aggregate rare counts и
co-occurrence combinations не гарантируют anonymity: публично по умолчанию только
FAIL_CLOSED/NONE и reviewed fixed reason categories после отдельного privacy review.

Target NewOutput держит exclusive new handle, не открывает existing file, но
не устраняет malicious concurrent namespace writer и не доказывает fsync/crash
durability. Output/compiler TEMP/OS logs могут писать на диск. Partial reservation
оставить для локального review, не unlink/reuse/overwrite, не менять ACL.

Collector child timeout90s не доказывает общий срок Git/filesystem/compiler и всех
descendants. Operator stall/resource stop plan обязателен; не убивать чужие
процессы, не запускать автоматический второй probe. Никаких изменений Windows,
Defender/Norton/ACL/services/registry/Grid/PG5432/MetaScalp или trading операций.

Полный physical G0 может стать PASS только после независимой приёмки всех
обязательных доказательств отдельным процессом. Сам адаптер намеренно **всегда**
FAIL_CLOSED/NONE/exit1 и не выдаёт enrollment. G1–G5 не разрешаются этим пакетом.

Фактический статус сейчас: **NOT_RUN / BLOCKED**. Единственный допустимый следующий
шаг — operator review пакета и заполнение независимых private provenance baselines.
