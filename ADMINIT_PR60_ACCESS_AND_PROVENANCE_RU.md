# PR60: read-only effective-access / independent provenance

Production target: PR60 HEAD `0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30`,
tree `a85846d46df6e95f3d757e25399d991ee1db872b`. Control base: PR64
`d45d9a0d21aa99cffb820c1247d45551b747c289`, tree
`ccad14fd76ba4d2a0d1f44fb3c5856f025e66eb4`. Exact new control HEAD/tree
фиксируются в отдельном review receipt / PR, не подменяют production target.

**Физически NOT RUN. G0 FAIL_CLOSED, authorization NONE, G1 NO-GO.**
Ни один synthetic PASS не разрешает observer. Этот инструмент не создаёт
каталоги/файлы, не меняет ACL/privileges/services/registry и не запускает
PowerShell/netsh/Git/compiler/PG/MetaScalp или другие дочерние процессы.

## Что реально измеряется

`scripts/g0_access_review.py` — stdlib CLI, два независимых режима:

1. По умолчанию сверяет фактические байты явно перечисленных файлов с externally
   approved manifest. Native DLL не загружаются этим режимом явно; сам Python
   и его стандартная библиотека уже используют свой runtime/OS APIs.
2. Только `--current-token`, только после совпадения всех manifest files:
   `scripts/g0_windows_access.py` читает security descriptor `C:\` и
   `C:\ProgramData` через held handles и выполняет Windows `AccessCheck`.

Запросы: CreateDirectories, CreateFiles, DeleteChild, DELETE, WRITE_DAC,
WRITE_OWNER, WRITE_ATTRIBUTES. Реальный process token дублируется с
SecurityImpersonation; существующая thread impersonation отвергается.
Нет AdjustTokenPrivileges, arbitrary SID/group simulation, logon/S4U/AD lookup
или тестового create/delete. Обе фазы и обе цели должны иметь один TokenId /
AuthenticationId / ModifiedId; file identity, descriptor digest и rights
before/after совпадают. Объекты открываются OPEN_EXISTING, READ_CONTROL и
READ_ATTRIBUTES, без FILE_SHARE_DELETE, с OPEN_REPARSE_POINT/BACKUP_SEMANTICS.
Root удерживается при открытии ProgramData; reparse отвергается.

Это **current-token descriptor access**, не полная симуляция kernel file-open:
не доказывает MIC, CAP/claims, endpoint policy, привилегированный доступ,
разрешение всего будущего path traversal или отсутствие concurrent mutation.
Root и ProgramData читаются последовательно, без атомарного snapshot обоих.
Reopen/сравнение не закрывает все races и ABA. Handle закрывается по окончании.
Нет обещания, что namespace останется тем же после завершения инструмента.
Необходим независимый review всей цепочки и действительной threat model.

### Главный предел: чужие effective rights

Текущий elevated admin token НЕ моделирует посторонний аккаунт или группу.
Нельзя вычислить effective rights простым OR Allow ACE, исключением «известных»
SID или созданием token только из SID: deny-only/restricted/logon groups,
owner rights и privileges меняют результат. `other_subjects: NOT_EVALUATED`
всегда. Инструмент НЕ выдаёт PASS отсутствия чужого DeleteChild.

Нужен отдельный Windows Effective Access review с корректным реальным
representative token / одобренным средством, учитывающим локальные и domain
memberships. Можно отдельно подготовить тот же read-only запуск в уже
разрешённой консоли представительного пользователя; этот runbook не выполняет
RunAs, не принимает credentials и не создаёт logon. Связь результата с
представительным аккаунтом reviewer фиксирует приватно; идентификатор не
публикуется. Неизвестные memberships/claims/rights => BLOCKED. Для arbitrary
посторонних субъектов полностью автоматического доказательства здесь нет.

## Проверяемая независимая provenance

Root of trust — независимо approved внешний verifier/managed review, а не
Python, который проверяет себя. До первого исполнения нужен authenticated
review receipt с exact source SHA/tree control, manifest SHA256 и approval
authority. Digest нельзя получать из этого же кандидата на ADMINIT и сразу
объявлять approved. В manifest не помещать секреты/DSN/токены; paths остаются
private. Этот проект не предоставляет выдуманный physical baseline.

Reviewer вне недоверенного collector:

1. Проверяет approved OS build/servicing catalog и Authenticode/signing chain
   либо authenticated signed distribution manifest; pin конкретных versions,
   files, publisher/authority, scope и content. Одного Valid недостаточно.
   Подпись .cat может покрывать файл без embedded signature.
2. Формирует exhaustive allowlist файлов реально используемого runtime и
   loader layout. Включает Python exe/DLL/stdlib/CRT, PowerShell/CLR, Git и его
   DLLs, системный netsh, native DLLs с dependencies, два новых control Python
   файла. Optional CSHARP_COMPILER не означает допуск Add-Type/R0.
3. Проверяет `._pth`, pyvenv.cfg, startup/loader configs, executable/module/DLL
   search, KnownDLLs, CWD/PATH/GIT_* config/includes/hooks/filters, module
   shadowing, MOTW и execution policy. Отсутствующие/динамические зависимости
   и отсутствие файлов тоже фиксируются в независимом loader review, а не
   скрываются отсутствием записи в manifest.
4. Аутентифицированно передаёт оператору exact manifest bytes + отдельный
   approved SHA256 и authority packet. Не генерировать его автоматически
   из фактических хешей на ADMINIT. Проверить сами control sources независимым
   approved Git/verifier до их запуска; самопроверка кода не bootstrap trust.

Manifest schema (private UTF-8 JSON, <=1MiB, no duplicate keys / NaN / Infinity):

| Поле | Контракт |
|---|---|
| schema | exact integer 1 |
| target_sha / target_tree | exact production PR60 values выше |
| files | непустой массив <=10000; ровно role/path/sha256/authority_sha256/basis у каждого элемента |
| role | все PYTHON_EXE, PYTHON_DLL, PYTHON_STDLIB, PYTHON_LOADER, CRT, POWERSHELL, GIT, GIT_RUNTIME, NETSH, DOTNET_RUNTIME, NATIVE_DLLS, CONTROL_CODE обязательны; несколько файлов на роль допустимы |
| path | абсолютный локальный drive path без UNC/ADS/.., device names, trailing space/dot; case-insensitive duplicates запрещены |
| sha256 | exact approved file digest, lowercase 64hex |
| authority_sha256 | SHA256 authenticated authority packet, 64hex; связь с actual authority проверяет внешний reviewer |
| basis | AUTHENTICODE / CATALOG / SIGNED_DISTRIBUTION |

Verifier проверяет ВСЕ записи до открытия файлов, потом читает реальные bytes;
несовпадение одной записи => UNAVAILABLE. Regular file, bounded size <=1GiB,
identity/size/mtime/ctime/link count до/после, non-reparse chain. System servicing
hardlinks допускаются ТОЛЬКО для записи CATALOG из независимо approved manifest;
для прочих basis nlink должен быть 1. Catalog approval должен охватывать aliases
и отсутствие writable-untrusted aliases. Файл с nlink>1 не становится безопасным
только из-за поля CATALOG. File hash одинаков для всех hardlink names; path-based
проверка не доказывает отсутствие concurrent writer или полный alias census.

`APPROVED_MANIFEST_BYTES_MATCH` означает только byte match с переданным pin.
Здесь нет независимой проверки signing authority, catalog membership, revocation,
actual loaded module set или полноты manifest. Signature verification выполняет
upstream approved reviewer. `loader_scope: INDEPENDENT_REVIEW_REQUIRED`, общий
`readiness: BLOCKED` сохраняются даже при совпадении всех файлов.

## Точные операторские шаги — подготовлены, не выполнены

Сначала read-only independent review из разделов выше и
[окончательного parent runbook](ADMINIT_PR60_FINAL_PARENT_RUNBOOK_RU.md).
Пока нет внешнего approval packet и решения оператора — STOP.
Не изменять execution policy, не использовать Bypass/Unblock/Add-Type.

В approved Windows PowerShell 5.1 x64 задать приватно approved absolute Python
и control checkout. Значения SHA/tree взять из exact final PR review receipt;
оставленные placeholders заведомо не дают допуска. В итоговом внешнем пакете
даны literal SHA/tree команды текущего control candidate.

```powershell
$ErrorActionPreference = 'Stop'
$ApprovedPython = 'C:\REPLACE_WITH_EXTERNALLY_APPROVED_PYTHON\python.exe'
$ControlRepo = 'C:\REPLACE_WITH_REVIEWED_CONTROL_CHECKOUT'
$ApprovedManifest = 'C:\REPLACE_WITH_PRIVATE_APPROVED_MANIFEST.json'
$ApprovedManifestSHA256 = 'REPLACE_WITH_EXTERNAL_APPROVED_64HEX'
$ControlExpectedSHA = 'REPLACE_WITH_REVIEWED_CONTROL_40HEX'
$ControlExpectedTree = 'REPLACE_WITH_REVIEWED_CONTROL_TREE_40HEX'
# Exact source/tool provenance must already be independently checked before Python.
if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
    -not [Environment]::Is64BitProcess -or $ApprovedManifestSHA256 -cnotmatch '^[0-9a-f]{64}$' -or
    $ControlExpectedSHA -cnotmatch '^[0-9a-f]{40}$' -or $ControlExpectedTree -cnotmatch '^[0-9a-f]{40}$') {
    throw 'BLOCKED_OPERATOR_INPUT'
}
# Phase 1 only: filesystem byte verification, no explicit native collector.
$ProvenanceStdout = @(& $ApprovedPython -B -E -s -S (Join-Path $ControlRepo 'scripts\g0_access_review.py') --manifest $ApprovedManifest --approved-manifest-sha256 $ApprovedManifestSHA256 2>$null)
$ProvenanceExit = $LASTEXITCODE
# STOP. Review privately; do not echo or automatically continue.
```

SHA/tree variables are review references, not silently assumed verified by this
snippet. Approved external Git/verifier must compare HEAD/tree, clean tracked and
untracked sources, and manifest-covered control files. Both production and control
must match their respective receipts. `-B -E -s -S` avoids bytecode writes/site/env
Python overrides; does NOT make an unapproved interpreter/loader trustworthy.

Only after separate positive provenance review AND explicit read-only access
decision, one additional operator-invoked command (no observer):

```powershell
$AccessStdout = @(& $ApprovedPython -B -E -s -S (Join-Path $ControlRepo 'scripts\g0_access_review.py') --manifest $ApprovedManifest --approved-manifest-sha256 $ApprovedManifestSHA256 --current-token 2>$null)
$AccessExit = $LASTEXITCODE
# STOP. No retry, directory creation, HTTP.sys/R0, enrollment or G1.
```

Expected diagnostic exit **1**, status FAIL_CLOSED, authorization NONE. Exit1
alone is NOT success evidence: require single complete JSON and expected schema,
target/source, provenance and access fields. `CURRENT_TOKEN_DESCRIPTOR_CHECKED`
is not foreign-subject clearance. Stdout contains only fixed labels and current
token rights booleans; no PID/SID/account/path/descriptor/raw exceptions. Keep
rights results local by default. No output file is created or overwritten; do not
redirect with `>` into evidence. If a private receipt is later saved, separately
approve new exclusive output and parent namespace, no stale file reuse.

## Runbook review / confirmed corrections

Previous blanket prohibition of any foreign CreateDirectories at ProgramData
was overstrict. It is separate from DeleteChild/rename/owner/DACL rights. Corrected
parent runbook preserves protected new-child DACL and forbids using any existing
directory, even an empty one with matching ACL. `DirectoryInfo.Create(security)`
is NOT exclusive and silently leaves existing directories unchanged. GUID and
Test-Path only reduce accidental collisions. If hostile precreation/concurrent
writer remains in scope, this creation path stays BLOCKED; no ad hoc helper or
new API is executed to bypass that limitation. No existing ACL/evidence cleanup.

## PASS / BLOCKED

| Boundary | Result before physical review |
|---|---|
| Synthetic schema/privacy/current-token adapter contracts | Local/hosted evidence separately reported in exact receipt |
| Production src/commissioning/VERIFIED | Unchanged from PR60 |
| Actual Windows API ABI/runtime correctness | NOT RUN; fake WinAPI tests do not prove ABI |
| Independent ADMINIT tool baseline / signatures / loader | BLOCKED, not supplied |
| Other-subject effective rights | NOT_EVALUATED / BLOCKED |
| Malicious precreation / TOCTOU-resistant directory creation | BLOCKED; current .NET path is not exclusive |
| New directory / observer / physical G0 | NOT RUN / FAIL_CLOSED |
| G1/deployment | NO-GO |

Stop on any unapproved provenance, missing file/role, reparse/identity/token/SD
change, unknown effective rights, parent DeleteChild/WriteDac/WriteOwner,
possible ancestor replacement, concurrent namespace writer, collision, partial
JSON, raw-data exposure or policy conflict. No automatic retry/repair/cleanup.

Primary sources:
[AccessCheck requires actual impersonation token](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-accesscheck),
[Authz SID context may omit logon groups](https://learn.microsoft.com/en-us/windows/win32/api/authz/nf-authz-authzinitializecontextfromsid),
[directory creation/no-op on collision](https://learn.microsoft.com/en-us/dotnet/api/system.io.directoryinfo.create?view=netframework-4.7.2),
[directory access masks](https://learn.microsoft.com/windows/win32/wmisdk/file-and-directory-access-rights-constants).
