# ADMINIT PR60 — preflight без физического запуска

**Пакет для review; ни одна физическая команда в этой работе не запускалась.**
Target: Draft PR60 HEAD `0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30`, tree
`a85846d46df6e95f3d757e25399d991ee1db872b`, parent/merge-base PR59
`b6aeaf99ea00c3550a87f9ecde74a4e73bd248fe`.

Новый control Draft PR содержит только offline evaluator, tests, docs и CI wiring.
Его точный SHA/tree фиксируется отдельно в итоговом receipt. Он **не заменяет**
target SHA в командах ниже. PR60 не меняется. `src/`, `commissioning/`, пять service
contracts и VERIFIED predicates остаются byte-identical PR60/PR59.

## Решение и границы

**Physical launch: BLOCKED**, пока отсутствуют independently approved provenance
baselines, свежие private host records и отдельное решение оператора. Готовность
документов к review не является допуском к исполнению. G1–G5 NO-GO.

`scripts/g0_preflight_contract.py` — offline проверка **утверждений** в записях,
а не collector, Authenticode verifier, attestation или launcher. Он не обращается
к Windows/HTTP/PG, не запускает Git/PowerShell/compiler и не создаёт enrollment.
Даже согласованные записи дают `FAIL_CLOSED`, `authorization: NONE`, exit **1**,
`readiness: READY_FOR_OPERATOR_REVIEW`, `evidence_authenticity: OPERATOR_REVIEW_REQUIRED`.
Поддельный согласованный JSON не становится настоящей host attestation.

Не использовать `commissioning/preflight.py` для этого этапа: его существующий
контракт требует authorization/enrollment и обращается к PostgreSQL и public REST.
Не запускать `collect-host.ps1`, enrollment/diagnose, installer, GUI или E2E.

## Bootstrap доверия: до запуска проверяемого Python

Проверка Python с помощью этого же непроверенного Python не независима. Оператор
сначала использует уже approved внешний verifier/управляемую среду и approved
Windows PowerShell. Если такого корня доверия нет — BLOCKED, не установка/repair.

| Компонент | Self-measured evidence, private | Необходимый независимый baseline |
|---|---|---|
| Python 3.12 x64 | Реальные image path/PE architecture/version/hash | Approved exact distribution/build и SHA256/certificate/catalog; version string недостаточна |
| python312.dll, CRT/UCRT, stdlib/zip | SHA256 каждого файла/manifest, принадлежность approved runtime | Signed distribution manifest / servicing catalog с проверенной authority и точным содержимым |
| Python loader/config | `._pth`, `pyvenv.cfg`, application dir, executable search, DLLs, environment, `.pth`/startup modules | Approved runtime/layout manifest; неизвестные loaders/venv/Store aliases запрещены |
| Windows PowerShell 5.1 x64 | Реальный системный executable, PE/version, assemblies | Approved Windows servicing/catalog baseline и exact signatures/hashes |
| Git и runtime | Executable, dlls, config/attributes/includes/environment и фактический executable search | Approved Git distribution/signature/catalog либо authenticated release manifest |
| System netsh | Exact System32 executable и dependencies | Approved OS build/servicing catalog; имя файла не является trust proof |
| .NET/C# backend для R0 | CLR/CodeDOM/provider/compiler/dependencies/resolution | Approved exact framework/assembly/compiler manifest; не guessed путь `csc.exe` |
| Native DLL chain | System32/KnownDLLs kernel32/kernelbase/ntdll/advapi32/psapi и dependencies | Approved OS servicing catalog и загрузочный namespace |
| Target source | HEAD/tree, clean source, actual bytes до/после | Independently reviewed immutable Git commit/tree + source-manifest digest; заранее approved LF/CRLF variants |

`Get-FileHash` показывает наблюдаемый digest, а не approval. Authenticode `Valid`
не равен approved publisher/build; strong name не заменяет signature/catalog.
Для unsigned component допустим только **заранее одобренный authenticated signed
distribution manifest**, привязывающий exact component bytes; голый unsigned
tool или `NOT_CHECKED` блокируется. Не скачивать/обновлять инструменты на ADMINIT.

Примеры metadata-only запросов в уже approved PowerShell, **не выполнены здесь**:

```powershell
$observedPolicies = Get-ExecutionPolicy -List
$observedEffective = Get-ExecutionPolicy
$hasProcessOverride = Test-Path Env:\PSExecutionPolicyPreference
$observedPS = $PSVersionTable.PSVersion
$observedLanguage = $ExecutionContext.SessionState.LanguageMode
$observedSignature = Get-AuthenticodeSignature -LiteralPath $approvedTool
$observedHash = Get-FileHash -LiteralPath $approvedTool -Algorithm SHA256
```

Все paths/certificate details/hash inventories остаются private; не выводить эти
объекты в чат/Actions/transcript. Signature chain/revocation/cache/network scope
должны быть одобрены; unknown/offline-incomplete не превращать в Valid.

### Python и executable/DLL loader

Только approved абсолютный **base** Python 3.12 x64; не `py`, Store execution alias,
случайный venv или `python` из PATH. Flags `-B -E -s -S`, без `-O`. Эти flags не
аттестуют executable, DLL loader или `._pth`; их проверить **до** interpreter launch.
`-I/-P` не добавлять к target collectors: существующие sibling imports требуют
reviewed commissioning directory. Не импортировать GUI/psycopg для G0.

Privately проверить Python/application directory, `python312.dll`, stdlib/zip,
CRT, `pyvenv.cfg`, `._pth` (включая `import site`), registry application paths,
startup/sitecustomize/usercustomize, ignored pyc/shadow modules, текущий каталог,
DLL search и loader-related environment. Не очищать environment глобально.

Target source binding вызывает bare `git`. Поэтому approved абсолютного Git в
ручной проверке недостаточно: реальное child executable resolution (application
dir/CWD/System/PATH), Git runtime/config/includes, fsmonitor/filter/external
helpers и GIT_* environment тоже должны быть одобрены до запуска. Не исполнять
непроверенный Git для проверки собственного доверия; не менять config ради PASS.

### Policy, Add-Type и temporary compilation

MachinePolicy/UserPolicy имеют приоритет над Process/CurrentUser/LocalMachine.
Требуются Process=Undefined, отсутствующий PSExecutionPolicyPreference override,
согласованный effective policy и FullLanguage. Любой Bypass, неизвестный scope,
неразрешённый policy/CLM/MOTW — STOP. Не применять `Set-ExecutionPolicy`, Bypass,
inline/encoded collector wrappers, `Unblock-File`, самоподпись или shell switch.

PR60 `.ps1` source не имеет embedded Authenticode signature blocks; это не
доказывает отсутствие внешнего Windows catalog. Approved catalog/signature evidence
для этих scripts не представлено: AllSigned сейчас **BLOCKED**. Не утверждать
подпись по одному имени файла либо считать отсутствие embedded block полной
host signature аттестацией. `scripts_signed=True` не может переопределить pinned
baseline `scripts_signed=False`; другой verified catalog потребует нового
independent baseline review, не boolean обхода. RemoteSigned допустим
только если текущие policy/MOTW и независимый source review разрешают эти bytes.

Format-only route не содержит Add-Type. R0 вызывает существующий `host-facts.ps1`
→ dot-source `process-evidence.ps1` → **Add-Type -TypeDefinition**. Это C#/.NET
компиляция P/Invoke collector, не новый C++/Visual Studio toolchain. Не запускать
Add-Type/`csc /?` или native probe для «проверки preflight». Compiler/backend и
точные assemblies должны быть заранее approved по metadata/provenance.

In-memory result assembly не доказывает отсутствие временных файлов: CodeDOM
может использовать TEMP/TMP, source/response/compiler diagnostics/assembly файлы.
Проверить существующие temp namespace, owner/writer scope, reparse/hardlinks,
свободное место, разрешённый write budget и cleanup ownership. Не менять ACL/TEMP
или удалять чужие файлы. Unknown backend/temp lifecycle блокирует R0, даже если
format-only отдельно допустим. Read-only означает отсутствие изменения системы,
а не zero disk/network/cache/OS logging I/O; crash durability не доказана.

## Source, host, PG и resources

Approved Git подтверждает target HEAD/tree/parent и tracked/untracked clean.
Ignored executable/pyc/DLL shadows проверяются отдельно. Actual source bytes
сверяются до и после с reviewed manifest, без редактирования/подписи/CRLF conversion
ради PASS. Source и output ancestors без reparse/UNC/alias и concurrent writers.

Host/user/token/elevation подтверждаются приватно; никаких auto-elevation,
SeDebugPrivilege/PPL bypass. Известный Grid/conflicting runtime — STOP. MetaScalp
не запускать/перезапускать; binary/signature/hash/version и fresh lifetime должны
быть independently approved/оценены. `/ping` и 17845 не ownership proof.

Existing PostgreSQL 5432/PGDATA отделены по read-only OS/service/listener metadata.
Никакого SQL, psql, pg_ctl, initdb, live DPAPI, cluster/DDL/DML, PG environment repair.
Unknown isolation — BLOCKED. CI PG18.1 на disposable runner не является host proof.

Нужны свежие CPU/RAM/free-disk baseline, sample scope и approved stop budgets.
Planning defaults: CPU>80%, RAM delta>1024MiB, free disk<8192MiB либо unknown — STOP.
Это не текущие измерения ADMINIT. Timeout child 20s/90s не доказывает total deadline
Git/filesystem/compiler/descendants; stall — STOP, без retry/следующего этапа.

## Output и offline record evaluator

Отдельные approved local absolute namespaces для baseline, records, preflight
receipt, format output и R0 output; вне checkout/runtime/private authorization.
Не публиковать hashes host tools, paths, SID, hostname, PID, DSN или session nonce.
Файл каждого output обязан отсутствовать. Никаких reused names/overwrite, UNC,
ADS, symlink/junction/reparse в ancestors, неучтённых hardlinks и competing writers.

Новый receipt writer проверяет ancestors, exclusive create, inode/file identity,
link count до/после write; не unlink/reopen/rename и не изменяет ACL. Ошибка может
оставить empty/partial reservation: сохранить локально, не retry. Existing target
и его hardlinks не открываются для write. Hostile concurrent same-user/admin
может обойти path checks между наблюдениями; это **не** доказанная защита от такого
writer. Невозможно исключить конкуренцию — BLOCKED.

Target format/R0 используют прежний `NewOutput` (exclusive held handle). Он
сохраняет existing files, но не проверяет approved ancestor namespace сам. Поэтому
одобрение и стабильность namespace обязательны до физического collector; новый
offline writer не меняет и не усиливает target executable автоматически.

Private JSON baseline: schema=1; source `{sha,tree,collector_manifest_sha256,
scripts_signed}`; tools keyed by COMMON/NATIVE roles из evaluator. Каждый tool:
`{sha256,authority_sha256,basis}`, где basis AUTHENTICODE/CATALOG/SIGNED_DISTRIBUTION.
Records: тот же source до/после + clean, tools + verification=VALID, mode, session,
recorded_at UTC epoch, versions, checks, namespace и policy из source/test schema.
Физических baseline/records в пакете **нет**. Synthetic test fixture не baseline.
Digest baseline берётся из независимого approved канала, не вычисляется в качестве
approval из проверяемого файла. Source manifest digest тоже требует review/approval.

Подготовленная команда offline review, **не выполнялась на ADMINIT**; `$controlRepo`
отдельно привязан к exact control Draft SHA/tree из receipt, `$g0Repo` остаётся PR60:

```powershell
$reviewStdout = @(& $g0Python -B -E -s -S (Join-Path $controlRepo 'scripts/g0_preflight_contract.py') --records $privateRecords --baseline $privateBaseline --approved-baseline-sha256 $independentlyApprovedDigest --expected-sha 0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30 --expected-tree a85846d46df6e95f3d757e25399d991ee1db872b --session $privateSession --output $newPreflightReceipt 2>$null)
$reviewExit = $LASTEXITCODE
```

Ожидается exit1 даже у согласованных records. Bootstrap error/нет полного нового
receipt/несогласованность stdout/file/source/session/freshness — BLOCKED. Не
публиковать `$reviewStdout` автоматически. READY_FOR_OPERATOR_REVIEW — только
review записей; отсутствие независимой host authenticity по-прежнему блокирует
запуск. Прошедшие записи нельзя переиспользовать дольше 300s или на другой session;
само поле времени не доказывает подлинность/отсутствие TOCTOU.

## G0 matrix

| Граница | Source/CI evidence | Physical статус сейчас / STOP |
|---|---|---|
| PR60 SHA/tree/base; 11 Actions / 29 ZIP | Перепроверяются независимо, exact receipt | Не host attestation |
| src/commissioning/VERIFIED equality PR59→PR60 | PASS при byte comparison | Не отменяет process/SCM evidence |
| Approved Python/PowerShell/Git/netsh/DLL baselines | Схема/negative tests | BLOCKED: реальные независимые baselines не представлены |
| Source loader/config/policy/MOTW | Source audit + malformed/refusal tests | NOT_ATTESTED; unknown/Bypass/unsigned+AllSigned → STOP |
| Native compiler/Add-Type/temp | Source audit; format route без compiler | NOT_ATTESTED; запрещает R0 без отдельного допуска |
| Output/aliases/exclusive create | Synthetic collision/hardlink/reparse/race tests | NOT_ATTESTED; concurrent writer/crash durability не доказаны |
| HTTP format-only | Отдельный runbook | NOT_RUN; не ownership/lifetime evidence |
| Native/SCM/lifetime/MetaScalp | Старые строгие predicates сохранены | NOT_RUN; unresolved → FAIL_CLOSED |
| PG5432 isolation / resources / operator scope | Обязательные private checks | NOT_ATTESTED; unknown → STOP |
| Полный physical G0 PASS | Не выдаётся этим evaluator | BLOCKED |
| G1–G5/enrollment/deployment | Не входят в пакет | NO-GO / authorization NONE |

## Первичные источники

- [PowerShell 5.1 execution policy](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1): scopes/precedence/AllSigned; policy не security boundary.
- [Add-Type 5.1](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/add-type?view=powershell-5.1): CodeDomProvider/compiler и in-memory assembly.
- [Get-AuthenticodeSignature](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/get-authenticodesignature?view=powershell-5.1): embedded/catalog signatures; не independent publisher approval.
- [Python 3.12 Windows](https://docs.python.org/3.12/using/windows.html): DLL/path/._pth configuration; startup flags не заменяют provenance.
- [CodeDOM TempFileCollection](https://learn.microsoft.com/en-us/dotnet/api/system.codedom.compiler.tempfilecollection?view=netframework-4.8.1): lifecycle temporary compilation files; не утверждается фактический backend ADMINIT без evidence.
