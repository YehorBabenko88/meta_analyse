# ADMINIT PR60 — одна HTTP.sys format-only попытка

**PREPARED / NOT_RUN.** Target HEAD `0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30`,
tree `a85846d46df6e95f3d757e25399d991ee1db872b`.

Выполнять только после полного применимого preflight из
`ADMINIT_PR60_G0_PREFLIGHT_RU.md`, проверки independent baselines и отдельного
явного решения оператора **именно на формат**. Не запускать автоматически и не
соединять с R0–R5 до/после в этой session. Preflight evaluator не launcher и не
допуск; unknown host/tool/source/policy/output состояние запрещает попытку.

## Scope

Один вызов существующего `commissioning/http_sys_format.py`. Внутри — один
approved System32 Windows PowerShell 5.1 child, `-NoProfile -NonInteractive -File`,
без ExecutionPolicy argument/inherited process override; системный netsh делает
`http show servicestate view=requestq verbose=yes`. Никакого Add-Type, native
process/SCM collection, DPAPI, PG, сети Bybit или изменения HTTP.sys.

Internal `http-sys-format.ps1` отдельно не вызывать и raw stdout/stderr не
перенаправлять. Они private/in-memory. Форматный observer не исполняет/переводит
локализованные labels, не устанавливает ownership или process lifetime.

## До единственного вызова

- Exact clean target + source hashes до запуска и approved Git executable search.
- Approved base Python 3.12 x64, loader, PowerShell5.1/System32 netsh; no aliases.
- Approved CLR/native DLL chain: elevation/system-directory WinAPI и PowerShell
  CLR остаются в этом route; отсутствие Add-Type не освобождает от их provenance.
- Existing scripts разрешены policy/MOTW, Process Undefined, no Bypass/override;
  AllSigned + unsigned target source → STOP, не inline copy/Unblock/shell switch.
- Private console, без transcript/debug/automatic log upload. Capture в private
  переменную; при bootstrap errors ничего raw не публиковать.
- `$formatOutput` — новый approved absolute local JSON; вне target/runtime/private
  authorization, leaf отсутствует, ancestors/links/writer scope проверены.
- Resources/output/timeout и stop plan согласованы. Native Add-Type/temp approval
  не нужен для этого route: он не разрешает последующую R0 попытку.

```powershell
$formatStdout = @(& $g0Python -B -E -s -S (Join-Path $g0Repo 'commissioning/http_sys_format.py') --expected-sha 0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30 --expected-tree a85846d46df6e95f3d757e25399d991ee1db872b --output $formatOutput 2>$null)
$formatExit = $LASTEXITCODE
# STOP: ни retry, ни второй netsh, ни R0–R5 после этой команды.
```

Команда подготовлена, не выполнена. Не echo `$formatStdout` без local schema/privacy
review. Наличие файла недостаточно; сравнить полный новый file/stdout/exit и source.
Output collision → отказ без overwrite; partial/close/source/bootstrap error → STOP,
сохранить локально reservation, не удалять/повторять ради результата.

## Ожидаемый отказ и privacy

Exit **1**, schema1, status **FAIL_CLOSED**, authorization **NONE**,
diagnostic_status HTTP_SYS_FORMAT_ONLY, lifetime_binding NOT_EVALUATED_DIAGNOSTIC_ONLY.
projection AVAILABLE означает только корректный aggregate format result.
`ownership=NOT_EVALUATED`, `format_support=NOT_ATTESTED` сохраняются даже при
английских markers. Не PID, URL, service/process names, paths, hostname или raw text.

Line/colon/marker counts идут широкими buckets; character flags — bool. target_token
PRESENT означает только вхождение статического числового token, **не listener/owner**.
Редкие structural combinations могут коррелировать с окружением: aggregate JSON
хранить локально; share только reviewed fixed status/reasons, не raw/private inputs.

PS child устанавливает свой Console.OutputEncoding=UTF8 для capture/JSON. Это не
изменение глобальной Windows code page и не доказательство исходного netsh byte
encoding. `$OutputEncoding=us-ascii` относится к native stdin pipeline и само по
себе не доказывает повреждения stdout. cp866/UTF8 и ru-RU observations исторические;
decoded Unicode не восстанавливает уже испорченные bytes и не придаёт неизвестным
заголовкам смысл. Unknown/localized/malformed/ambiguous layout остаётся unsupported.

`/ping`, порт 17845, успешный netsh, кириллица или отсутствие английских markers
не являются ownership proof. Не добавлять переводы «по догадке». Результат этой
попытки не разрешает G0 PASS/enrollment/G1 либо автоматический native probe.

## Завершение

Один attempt → STOP/operator review. Ничего не запускать/перезапускать и не менять
HTTP.sys/MetaScalp/Windows/Norton/Defender/ACL/services/registry/PG. Timeout child20s
не гарантирует total Git/filesystem/process-creation deadline; stall не повод retry.
No installation rollback; только approved own evidence, existing files не удалять.

Фактический статус этого пакета: **NOT_RUN / BLOCKED до physical preflight**.
