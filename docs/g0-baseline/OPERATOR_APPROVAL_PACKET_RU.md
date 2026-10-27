# Внешний baseline packet — DRAFT / NOT APPROVED

Это шаблон процедуры утверждения, НЕ approved baseline ADMINIT. Никакие реальные
hashes/paths/SID/host records не собирались и не заполнялись автоматически.
Production PR60: `0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30` /
`a85846d46df6e95f3d757e25399d991ee1db872b`. Immutable control base PR66:
`419d336480d9ec3b40a8bc96a402874f434cc3c5`. Новый control HEAD/tree берутся
из отдельно проверенного final receipt. PR66 не изменяется.

## Разделение объектов доверия без circular hashes

1. Compact authority reference packet (<=1MiB): references approved OS/vendor servicing catalogs, signing
   certificates/chain policy, authenticated signed distribution manifests и
   scope; большие catalog/distribution payloads проверяются отдельно, не
   конкатенируются в packet. Никакого self-signed collector approval. Его SHA256 = A. Этот packet
   не должен содержать digest результирующего manifest, чтобы избежать цикла.
2. Private file manifest: exact files/roles/digests и authority_sha256=A у всех
   записей. Его SHA256 = M. Manifest template `MANIFEST_NOT_APPROVED.json`
   имеет пустой files и заведомо не проходит verifier. Его нельзя объявлять
   approved простым вычислением локального digest.
3. Отдельный операторский approval receipt связывает M, A, control SHA/tree,
   production SHA/tree, external approver verification method, policy/scope,
   время действия и остаточные BLOCKED. Подпись/authority этого receipt
   проверяется независимым approved verifier/каналом, не самим Python collector.
   Authenticated approver передаёт M/A оператору отдельно от файлов.

Новый verifier сравнивает реальные bytes с M/A и references; он НЕ проверяет
криптографически подпись approver, revocation, status APPROVED, timestamp или
полноту loader scope. Даже корректно подписанный receipt нельзя заменить на
`approval=true` в JSON. Все runtime результаты остаются FAIL_CLOSED/NONE/BLOCKED.

## Что должен проверить approver до первого запуска Python

| Scope | Independent approval evidence |
|---|---|
| Python3.12 x64 executable, python312.dll, stdlib/CRT | Exact signed distribution/build/files; exe flags alone не root of trust |
| PowerShell5.1 x64 / CLR | Exact OS/framework servicing catalogs, actual executable/module resolution, execution policy/MOTW |
| Git/runtime | Exact distribution + executable search/config/includes/hooks/filters/GIT_* review; no executable side effects from source verification |
| netsh/native DLL chain | Exact system binaries/KnownDLLs/catalog/OS build/dependencies; имя System32 не identity proof |
| CONTROL_CODE | Both new scripts и их импортируемые source files в exact reviewed checkout, no shadow modules/untracked code |
| Loader | DLL paths/CWD/PATH, ._pth/pyvenv.cfg, startup modules, absence/config evidence; список только существующих файлов не доказывает отсутствующие dependencies |
| Servicing hardlinks | Catalog-backed aliases/ownership/effective writes review; nlink/hash не полноценный alias census |
| Authority | Approved signer/root/channel, actual signature/catalog validation independent of collector; self-measured hashes отдельно |

Reviewer privately fills expected file rows from authenticated upstream records.
Не клонировать ADMINIT filesystem hashes в «эталон» и не подписывать неизвестный
host state задним числом. Фактические ADMINIT observations можно позже сравнить
с уже утверждённым baseline; mismatch => STOP, не auto-refresh baseline.

## Approval checklist / stop conditions

- [ ] Exact control/prod source and clean worktree independently checked.
- [ ] Scope complete, origins/signatures/catalog membership and authority checked.
- [ ] M/A delivered separately through approved authenticated channel.
- [ ] Python/PowerShell/loader policy approved before executing them.
- [ ] Recipient verifies receipt authenticity and validity independently.
- [ ] Unknown other-subject rights and namespace/concurrency remain BLOCKED.
- [ ] Explicit operator decision is limited to one specified read-only mode.

Ни одна галочка в этом репозитории не установлена автоматически. Неизвестность,
подмена pin/file/scope, signature failure, stale approval, неучтённый loader,
policy conflict => STOP. Не использовать Bypass/Unblock/Add-Type/новые логины.
Template receipt `APPROVAL_RECEIPT_NOT_APPROVED.json` содержит NOT_APPROVED
placeholders и НЕ является authority. Пустые/черновые templates не подавать
как approved inputs; необходимость их заполнения не разрешает physical run.

## Подготовленные команды, не исполнены

После независимого review использовать точный operator runbook
`ADMINIT_PR60_ACCESS_AND_PROVENANCE_RU.md`. Provenance-only команда читает file
bytes; при необходимости отдельной проверки reference можно добавить
`--authority-packet <private packet> --approved-authority-sha256 <external A>`.
Optional --current-token требует оба pin/reference, отдельное операторское
решение и всё равно не является G0 PASS. Никакого создания каталога/observer/G1.
