# S1-PRECHECK: один read-only цикл

Статус: implementation/source/synthetic acceptance отдельно от physical admission.
S0 PR73 уже сообщил физический PASS4589ms; S0 повторять не нужно.
Production target PR60 не меняется; source-continuity target — точный PR73:
`b00c66776b27e929016f7541329c29c9349dddfe`, tree
`0418dc7bea4bb2f40f6712b0f3c0c1a6c63b8288`.

## Scope

Новый control packet не запускает `local_smoke.py`, Git или проектные imports.
Это НЕ реализация полного S1/G0 и НЕ повтор S0. Результат только
`PASS_PRECHECK_ONLY`, `s1_complete=false`, authorization NONE, G0 FAIL_CLOSED.
Не запускаются UI, Bybit, netsh, SCM, collector, PostgreSQL или G1.

Три файла control packet, из одного отдельно проверенного immutable HEAD:
`Invoke-S1Precheck.ps1`, `s1_precheck.py`, `s1_source_reference.json`.
Не запускать скопированный worker напрямую; до исполнения нужны pin-check
launcher и внешнее операторское решение. Проверка PID/ack — cooperative guard
против mislaunch/wrapper, не аутентификация supervisor/оператора.

Source manifest получен из752 blob точного Git tree PR73 в development;
в нём SHA256 каждого raw tracked файла. Он не включает новый control packet.
В source namespace PR73 проверяются байты всех этих файлов дважды, без исполнения.
`source_sha/tree` в receipt означают binding к этому immutable content reference;
это не запрос текущего Git HEAD/index и не clean-worktree attestation.
Untracked/ignored файлы не исполняются и не включены в source predicate.
Raw CRLF/LFS transformations, reparse/hardlinks source или mismatch блокируются.

Runtime: supervisor ДО Python запуска сверяет private packet pin и selected
runtime hashes, отсутствие заданных startup files и environment. Worker повторяет
проверки runtime до/после финального source scan, проверяет accepted V2 receipt.
Полный Lib не перечитывается: prior V2 PASS используется повторно только при
явном операторском подтверждении неизменности namespace. Это snapshot assurance,
не continuous hostile-writer exclusion или полная Windows loader attestation.

## Внешний private continuity packet — без автоматического baseline

Нужен отдельный UTF-8 JSON, одобренный независимым approver/оператором вне
автоматического adapter. SHA256 этих exact bytes передаётся отдельно через
доверенный канал. Hash и switch сами не создают approval authority.
Не генерировать expected runtime hashes из текущих ADMINIT observations.
Использовать ранее независимо принятые vendor/reference hashes; отсутствующие
references означают BLOCKED. OS/PowerShell bootstrap принимается явно по политике
оператора; adapter не создаёт ему доверенность. Development fixtures не baseline.

Точная схема верхнего уровня:

```json
{
  "schema": 1,
  "reference_kind": "EXTERNALLY_REVIEWED_CONTINUITY",
  "source_sha": "b00c66776b27e929016f7541329c29c9349dddfe",
  "source_tree": "0418dc7bea4bb2f40f6712b0f3c0c1a6c63b8288",
  "files": [{"role": "python_exe", "path": "<approved absolute private path>", "sha256": "<independent accepted SHA256>"}],
  "absent": ["<approved absent startup path>"],
  "environment": {"PATH": "<approved private value>"},
  "mapping_receipt": {"path": "<accepted V2 JSON receipt>", "sha256": "<approved receipt bytes SHA256>"}
}
```

Пример намеренно неполный и НЕ executable approved baseline.
Все16 required roles должны встречаться ровно один раз:
python_exe, python312_dll, hashlib_pyd, ctypes_pyd, libcrypto, libffi, crt,
bz2_pyd, lzma_pyd, git_exe, git_core, libiconv, libintl, pcre2, zlib, powershell_exe.
Допустим ещё crt_1. git_exe/git_core могут указывать на один принятый core;
если выбран wrapper, оба соответствующих vendor images обязательны.
Python — принятый direct official executable, не новый venv/wrapper.
PowerShell path должен совпасть с реально выполняющим supervisor image.
Штатные runtime hardlinks допускаются только при exact reference hash;
для source hardlinks запрещены. Ничего по этим ссылкам не записывается.

environment содержит РОВНО PATH, GIT_CONFIG_SYSTEM, GIT_CONFIG_GLOBAL,
GIT_CONFIG_NOSYSTEM, PYTHONHOME, PYTHONPATH, PYTHONSTARTUP, PYTHONUSERBASE,
__PYVENV_LAUNCHER__. Значения строка или null (absent); не публиковать их.
absent:1..16 точных ранее reviewed startup paths, включая applicable ._pth/
pyvenv.cfg; не подменять произвольным отсутствующим файлом.
mapping_receipt — сохранённые exact bytes успешного V2 JSON с2397 Lib, matching
cache count,2 native, zero refusal/errors и authorization flags. Это observed
receipt, не vendor reference. Его привязку к тем же launch paths/state утверждает
реальный approver. Полный Lib mapping повторно не выдаётся за измеренный здесь.

## Preconditions и бюджет

- Exact control HEAD/tree, три code/reference hashes и hosted synthetic acceptance
  проверены отдельно; source PR73 и accepted runtime namespace неизменны.
- Никакого known concurrent installer/update/checkout/writer; отсутствие hostile
  writers не выводится из одного ACL snapshot.
- Только approved local fixed NTFS paths и trusted Windows/PowerShell bootstrap;
  никакого UNC/remapped remote drive. Никаких profile/policy bypass.
- Новое явное approval ОДНОЙ S1_PRECHECK попытки, не S1/G0/G1.
- stdout-only; ни новых directories, evidence files, private observation,
  authorization files, cache writes, ACL/config changes.

Одна попытка, retry0;30s monotonic budget;5s per bounded file read;
10000unique metadata paths,128MiB суммарных worker reads,16MiB/file;
4096bytes stdout/stderr capture, один approved direct Python worker.
Supervisor проверяет working/private memory<=256MiB, pins CPU affinity к одному
доступному logical CPU. Worker ждёт финального ack, чтобы resource checks не
пропускали нормальный fast exit. Child creation/network/FFI events запрещены
worker audit hook. Это tripwire, не sandbox для malicious native/runtime.

Resource stop conditions проверяются watchdog polling; это не OS hard memory quota.
Metadata/File.Open calls и uninterruptible Windows I/O могут задержать сам
supervisor:30s НЕ real-time OS termination guarantee. Budget расходуется и до
Start; после истечения новый worker не запускается. Если policy требует hard
OS-wide sandbox/termination всех malicious descendants — текущий packet BLOCKED.

## Одна физическая команда — НЕ выполнять до отдельного допуска

$ControlPacket — отдельно проверенные три файла нового candidate;
$Repo73 — неизменный source checkout PR73; $PythonExe — approved direct Python;
$ContinuityPacket/$ContinuityPacketSha256 — reviewed private packet и его pin.
Проверка launcher hash выполняется оператором по отдельно доставленному reference
до команды. Ни одно из этих значений не берётся автоматически из ADMINIT hashes.

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -File (Join-Path $ControlPacket 'Invoke-S1Precheck.ps1') -Repo $Repo73 -Python $PythonExe -Packet $ContinuityPacket -PacketSha256 $ContinuityPacketSha256 -OperatorApproved
```

PASS только exit0 + PASS_PRECHECK_ONLY + PRECHECK_COMPLETE + source_bound=true,
source/runtime/output predicates PASS, exact PR73 content-reference SHA/tree.
Все остальные results/timeout/missing receipt/неожиданный child => FAIL/BLOCKED,
STOP; не повторять для достижения PASS. На startup failure stdout может
отсутствовать: отсутствие receipt никогда не PASS.

После любого результата STOP и независимый review только aggregate JSON+exit.
При зависании не запускать второй экземпляр; operator recovery по отдельному
решению, без удаления чужих файлов/завершения unrelated процессов.
Следующий этап автоматически не разрешается. S0 повторно не запускать.

## Source review / RED-GREEN

Независимый review прототипа выявил execution-before-verification, fast-exit
resource gap, escaped duplicate JSON, missing WinAPI child tripwire и поздний
runtime drift. Они закрыты prelaunch binding, PID/ack, strict ASCII receipt,
_winapi event, повторной runtime проверкой и deadline check перед Start.
Негативные fixtures включают эти сценарии; физический S1 не исполнялся.
Exact-head tests/artifacts и remaining approval blockers — в итоговом отчёте
к Draft PR, а не в self-measured baseline на ADMINIT.
