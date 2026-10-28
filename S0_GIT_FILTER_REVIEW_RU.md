# S0 Git filter guard — отдельный candidate от PR71

Immutable base PR71 `1c875fc1b265c860bdf5d159488f8e1241fb0def`, tree
`b844dfb8a74b37138629a913118a9f70f190e5e9`. PR60/68/71 не меняются.

Configured LFS filter сам по себе не означает применение. Но один attributes
file с LFSRules=0/OtherFilterRules=0 не покрывает system/global attributes,
info/attributes, nested .gitattributes и macros. Их actual ADMINIT scope по
предоставленным observations не установлен. Source review не подменяет эту
проверку и не запускает physical commands.

## Воспроизведённый риск и минимальная защита

PR71 source разрешает Git clean/process callbacks во время status при active
filter attributes, хотя основной S0 child фиксирован и isolated. На собственном
synthetic repo подтверждено: file bytes не меняются, status остаётся clean,
но filter пишет synthetic marker. Проверены direct/macro attributes и active
system/global/local/worktree/conditional includes. Не утверждается, что filter
на реальном ADMINIT активен: там это пока неизвестно.

Перед каждой source-check phase новый candidate читает только имена effective
filter keys через Git config --includes --null --name-only --get-regexp.
Для <=16 безопасно представимых driver names передаёт только command-line -c:
clean=, smudge=, process=, required=false. Persistent config/attributes не
меняются. Пустые commands не запускаются согласно Git convert.c. --no-pager,
existing fsmonitor=false, hooksPath=NUL и no-optional-locks сохранены.

Malformed/truncated/oversized/error query => BLOCKED до status/Python. Наличие
configured LFS НЕ блокирует само по себе. Если raw worktree без фильтра
отличается от index, status dirty => BLOCKED; не нормализовать ради PASS.
GIT_CONFIG запрещён при наличии даже пустого значения: этот legacy override
меняет только git config query, но не другие commands; иначе discovery/status
могли бы читать разные config. Прочие effective scopes не отключаются и не
редактируются; их selected filter keys читаются через native Git resolver.
Git-version2.55.0.windows.5 empty-command behavior проверен по upstream source,
а тесты выполняют real Git только на локальных/hosted synthetic repositories.

Это snapshot guard известных effective drivers, НЕ sandbox malicious Git,
race-proof config protocol или proof отсутствия hostile writers. Active
conditional include определяется Git для каждого текущего invocation;
новый неизвестный driver между discovery/status, unreviewed submodule configs,
UNC includes/loader hooks и неизвестные helper mechanisms требуют отдельного
stable namespace/runtime scope. Для fixed MetaAnalyse checkout expected tree
не имеет gitlinks; произвольные submodule repositories не принимаются как
автоматически approved. S0 Git commands не вызывают diff/checkout/fetch/remote.

## Минимальный operator-only Git review (не выполнен)

После independently approved Git executable/runtime и existing trusted shell:
приватно установить actual gitdir/common-dir и effective config origins/scopes,
включая system, XDG/global, local config, config.worktree при включённом
extensions.worktreeConfig, active/inactive conditional include candidates.
gitdir/gitdir-i/onbranch/hasconfig conditions оцениваются в exact namespace.
Не публиковать origin paths, command values, URLs, credentials или raw configs.

Attributes priority: info/attributes выше directory-local .gitattributes;
ближайшие к path patterns выше parent/root; global/system ниже. Поздние
assignments переопределяют по attribute. Проверить macros не regex подсчётом,
а effective Git attribute evaluation всех relevant tracked paths; untracked
attrs/config тоже могут менять результат. Macros определяются в допустимых
top-level/global/system/info locations; nested patterns могут их применять.

Подготовленные read-only commands после такого Git approval, output только
в private variables, без записи config или запуска status:

```powershell
$ConfigPrivate = @(& $ApprovedGit --no-pager --no-optional-locks -C $Repo config --includes --show-origin --show-scope --null --list 2>$null)
$ConfigExit = $LASTEXITCODE
$TrackedPrivate = @(& $ApprovedGit --no-pager --no-optional-locks -C $Repo ls-files -z 2>$null)
$TrackedExit = $LASTEXITCODE
# STOP. Do not print these variables or pipe filenames via lossy PS5.1 ASCII stdin.
# A binary-safe approved reader must feed exact NUL-delimited paths to:
# git check-attr --all -z --stdin
```

check-attr вычисляет attributes, не вызывает content filters; нельзя подменять
его grep по одному файлу. PowerShell native pipeline default encoding и NUL
разбиение могут испортить path coverage: не заявлять полный coverage по этому
сокращённому snippet. Namespace/token/time/source binding остаются independent
review обязанностью. Никаких config reset/unset, ACL changes или retries.

## Signer/distribution reference

Официальный upstream release v2.55.0.windows.5 публикует SHA256 MinGit64 ZIP:
`56d7b226b7693196cfc71fef26568f536c4a021ab6c37ff2db4287bed908e96e`.
Archive скачан в development workspace и совпал с published digest; binaries
не запускались. Из cmd/git.exe и mingw64/bin/git.exe получены valid signatures:
subject `CN=Johannes Schindelin, O=Johannes Schindelin, L=Bruehl, C=DE`,
certificate thumbprint `2A1E97CBF0DFCDA15B0DA0AC9745014F989D4AD0`.
Это независимо полученный vendor reference для этого MinGit asset, не actual
ADMINIT signer attestation и не автоматическое назначение approved publisher.
Не переносить MinGit package proof на любую installed Git layout без сравнения.

Actual ADMINIT signer ещё не сопоставлен с approved reference. Version string
и Authenticode Valid недостаточны для runtime approval. Аналогично seven
crypto/FFI Valid observations не являются approved file/path/loader baseline.
No self-measured ADMINIT hash превращён в expected baseline.

## Verdict

Оригинальный PR71: S0 physical **BLOCKED** до полного S0 Git config/attribute
scope либо отдельного принятия hardened candidate, signer/distribution/runtime
match и explicit operator approval. Новый candidate уменьшает callback risk,
но не выдаёт runtime authority. Все S1–S4 BLOCKED; G0 FAIL_CLOSED/NONE.
Никаких физических S0/G0/observer/PG/ACL/config changes не выполнялось.

[Upstream release](https://github.com/git-for-windows/git/releases/tag/v2.55.0.windows.5),
[Git attributes precedence/macros](https://git-scm.com/docs/gitattributes),
[Git2.55 convert.c filter dispatch](https://github.com/git-for-windows/git/blob/v2.55.0.windows.5/convert.c).
