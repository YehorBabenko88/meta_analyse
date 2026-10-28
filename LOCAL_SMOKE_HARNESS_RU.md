# Минимальный local smoke harness S0

Base control PR68 HEAD `d63f79e3cab8c6c207afa6537535655c2291e38d`, tree
`f0ec4f443f74d217bd56c0f39ce94c3688cf3bb9`. Production target PR60
`0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30` /
`a85846d46df6e95f3d757e25399d991ee1db872b`. Эти PR не изменяются.
Новый exact control SHA/tree берётся из final Draft PR receipt, не из base68.

Реализован ТОЛЬКО S0: один фиксированный isolated Python child импортирует
json/hashlib/hmac/pathlib/ctypes, проверяет Python3.12 x64 и flags. Никаких
Windows identity APIs, AccessCheck, host inventory, HTTP.sys, compiler/Add-Type,
database/UI/Bybit/network или application imports. Import может загружать
нативные runtime dependencies; их authenticity не доказывается успешным import.
На физическом ADMINIT в разработке ничего не запускалось.

## Контракты этапов, без автоматического перехода

|Stage|Разрешённая цель|Отдельный gate|Сейчас|
|---|---|---|---|
|S0|Python isolated import smoke|Exact source, independently reviewed runtime/loader и explicit S0 operator decision|IMPLEMENTED|
|S1|Read-only G0|S0 witness + независимый G0 допуск/source/host evidence|UNIMPLEMENTED / BLOCKED|
|S2|Только isolated PostgreSQL55480|S1 acceptance + отдельный G1 approval, ownership/attestation/rollback,5432 не трогать|UNIMPLEMENTED / BLOCKED|
|S3|Synthetic Desktop/UI|Предыдущие stage witnesses + explicit UI scope, offscreen/test data, без production writes|UNIMPLEMENTED / BLOCKED|
|S4|Public Bybit read-only E2E|Отдельные network/E2E/storage approvals и previous stages; no trading keys/orders|UNIMPLEMENTED / BLOCKED|

S1–S4 не содержат executable callbacks. Их выбор, даже с operator flag,
возвращает BLOCKED/exit2 без любого дочернего процесса. Previous receipts не
считаются автоматическим approval и не принимаются этим минимальным S0 как
enrollment. Нет batch/all/retry/resume/автоматического stage planner.

## Receipt и результаты

Один JSON в stdout, <=2KiB, allowlisted labels + hex source refs + elapsed_ms и
exit codes. Raw stdout child/Git, stderr/exceptions, paths, PID/SID/hostname,
environment/DSN/tokens/module paths не публикуются. Git source before/after:
HEAD/tree/clean worktree, absolute explicitly selected Git, no optional locks,
fsmonitor/hooks disabled for invocation. Git/runtime/config/attributes/loader
должны быть externally approved: это не OS sandbox против malicious Git/config.
source_bound относится к supplied checkout и двум Git snapshots, не доказывает
identity уже загруженного interpreter/harness или отсутствие ABA/writers.
Оператор проверяет bytes самого harness и связь command path с reviewed repo
до запуска; произвольный JSON/library call не является authenticated receipt.

- PASS_SMOKE_ONLY/exit0: fixed imports/flags observed и source before/after match.
- FAIL/exit1: S0 child failure, malformed output или source drift после child.
- BLOCKED/exit2: missing operator decision, bad input/source или S1–S4.

Всегда authorization NONE, g0_status FAIL_CLOSED, next_stage BLOCKED,
approval_authenticity EXTERNAL_REVIEW_REQUIRED. `source_bound=false` означает,
что SHA/tree лишь caller expectations, не подтверждённый source. Неверные refs
не копируются в receipt и становятся null. Invalid CLI receipt тоже BLOCKED.
Пустой/частичный JSON или отсутствие receipt не является PASS.

elapsed — фактически измеренный wall duration, не обрезается для красивого
порога. Soft overall budget15s: Git call<=2s, child<=8s с оставшимся временем.
OS process creation/termination может превышать timeout; hard real-time/drain
descendants/memory sandbox не заявляются. stdout capture проверяется по размеру
после communicate; bounded receipt не означает bounded capture memory при
malicious approved executable. Никаких retry; максимум один S0 child.

Никакого сохранения файлов/evidence этим harness, ни truncate/cleanup/rename,
ни создания каталога. stdout не перенаправлять поверх старого receipt. Если
нужно сохранить, отдельно reviewed exclusive namespace/writer; persistence и
crash durability этим минимальным S0 не реализованы. Не использовать старый
PASS при новом source/session. Новый approved baseline не генерируется.

## Подготовленная operator-only команда — НЕ ВЫПОЛНЕНА

Оператор сначала независимо проверяет source/runtime/loader, CWD/env и Git
namespace по existing PR68 approval protocol. Флаг --operator-approved-s0 —
caller assertion отдельного решения, НЕ криптографическая проверка authority.
Нельзя исполнять непроверенный Python, чтобы впервые доказать trust этого Python.
-I изолирует Python paths/environment/site, но не все native DLL/config/hooks.
No policy/ACL/PATH/encoding changes, no Bypass/Unblock/Add-Type.

```powershell
$ApprovedPython = 'C:\REPLACE_WITH_REVIEWED_PYTHON312_X64\python.exe'
$ApprovedGit = 'C:\REPLACE_WITH_REVIEWED_GIT\git.exe'
$Repo = 'C:\REPLACE_WITH_REVIEWED_NEW_CONTROL_CHECKOUT'
$SHA = 'REPLACE_WITH_FINAL_NEW_CONTROL_HEAD'
$Tree = 'REPLACE_WITH_FINAL_NEW_CONTROL_TREE'
# Only after explicit operator S0 decision; capture privately, no file write.
$S0Stdout = @(& $ApprovedPython -I -S -B (Join-Path $Repo 'scripts\local_smoke.py') --stage S0 --repo $Repo --python $ApprovedPython --git $ApprovedGit --expected-sha $SHA --expected-tree $Tree --operator-approved-s0 2>$null)
$S0Exit = $LASTEXITCODE
# STOP. Review one complete receipt and exit code. No automatic second command.
```

Parent harness CLI тоже требует -I -S -B, иначе operator assertion не активируется.
Тесты используют только mock source/runtime failures и один local/hosted
isolated import child, не ADMINIT inventory. Каждая physical попытка требует
нового explicit решения; fail/blocked/timeout — STOP, без исправления среды.
