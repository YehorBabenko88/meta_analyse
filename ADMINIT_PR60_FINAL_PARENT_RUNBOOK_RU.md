# ADMINIT PR60 — окончательный runbook нового приватного parent

Target PR60 HEAD `0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30`, tree `a85846d46df6e95f3d757e25399d991ee1db872b`. Подготовлено 2026-10-27, без выполнения на ADMINIT.

Этот документ заменяет прежнее blanket-требование отсутствия любого CreateDirectories у посторонних субъектов в родителе. Остальные требования конфиденциальности и независимой source/tool provenance сохранены. G0 FAIL_CLOSED, authorization NONE; G1 NO-GO. Никакой observer этим runbook не запускается.

## Решение по новым наблюдениям

Предложение ровно одно: НОВЫЙ `C:\ProgramData\MetaAnalyse-G0-Private-<случайный GUID>`, protected DACL, owner CURRENT_USER, только CURRENT_USER/SYSTEM/ADMINISTRATORS. Это выделенный parent будущих G0 evidence, а не существующий application directory. Фактический GUID остаётся приватным. Никакой каталог не выбран автоматически и не считается одобренным.

`C:\ProgramData` — только условный bootstrap parent. CreateDirectories посторонней встроенной группы само по себе НЕ причина отказа: оно разрешает создание соседнего child, а не чтение или изменение защищённого child. Но наблюдения не доказывают отсутствие других effective rights. Сначала независимый review ниже. Если он не пройден — BLOCKED; не переходить к случайному из 19 LOCALAPPDATA-кандидатов.

Непустые существующие каталоги приложения и MetaAnalyseCommissioning не использовать и не очищать. C:\MetaAnalyse-Test с дополнительным Modify пока не одобрен: требуется разбор applies-to и effective rights; исправлять его ACL запрещено этой процедурой.

## Threat matrix и критерий допуска

| Свойство | Реальная угроза / решение |
|---|---|
| CreateDirectories на bootstrap parent | Само по себе не раскрывает child; позволяет precreation/DoS, а не автоматический доступ к успешно созданному protected child |
| Parent DeleteChild | Может позволять удаление/rename child независимо от отсутствия DELETE у child; посторонний effective доступ такого рода => STOP |
| DELETE/WRITE_DAC/WRITE_OWNER на parent или предках | Подмена пути/изменение доверенной цепочки; проверить также DeleteChild на родителе каждого предка и owner, который может менять DACL; неизвестность => STOP |
| Child inheritance | Защищённая DACL задаётся ПРИ создании с SetAccessRuleProtection(true,false); не создавать с inherited ACL для последующего Set-Acl |
| Precreation/collision | DirectoryInfo.Create(DirectorySecurity) при existing directory ничего не делает, не сообщает надёжно «создал я». Проверка отсутствия и GUID снижают случайный риск, но не заменяют exclusive primitive |
| TOCTOU | Проверка имени до/после не атомарна. При допустимом hostile concurrent creator в bootstrap parent эта .NET-процедура НЕ доказана безопасной; STOP, требуется отдельно reviewed exclusive native/helper implementation, не Add-Type ad hoc |
| Concurrent trusted writers | CURRENT_USER/SYSTEM/admin входят в trust boundary. Если не исключены их конкурентные изменения namespace — STOP |
| Junction/reparse/mount/subst | Отвергать всю цепочку, проверить drive mapping отдельно; отсутствие reparse флага на одном child недостаточно |
| Hardlink | Относится к leaf-файлам; новый пустой parent не доказывает будущий nlink=1. Existing leaf не переиспользовать |
| Privacy | Только три доверенных SID в child; отсутствие Write у постороннего НЕ оправдывает Read. Parent listing может раскрывать сам факт/имя каталога; GUID не содержит hostname/user/service, но не обеспечивает анонимность |

Важное различие: отсутствие всемирного запрета CreateDirectories не означает доказанную безопасность path-based Create против malicious precreator. Для однократного контролируемого bootstrap оператор отдельно утверждает отсутствие такого writer на коротком этапе создания и review. Одной галочки без основания недостаточно. Если модель требует устойчивости к активному локальному противнику, этот runbook BLOCKED.

## Независимый operator review — до любой записи

Reviewer не должен принимать self-measured hash/собственное утверждение evaluator за внешний baseline. Проверить точный target SHA/tree, clean worktree и approved Python/PowerShell/.NET/Git/loader/catalog/signatures по внешнему approved manifest. Не выполнять collector/Add-Type/native probe для этой проверки. Нет approved baseline — STOP.

В approved PS5.1 x64 с разрешённой политикой, без Bypass/Unblock и обхода AllSigned: приватно прочитать owner и DACL `C:\` и `C:\ProgramData` через `Get-Acl -LiteralPath`, проверить owner входит в approved trust boundary, canonical DACL и отсутствие неожиданных ACE/изменений. Защищённость DACL сама по себе не означает безопасность. Проверить LOCAL NTFS, не redirected drive, reparse/mount/junction цепочку. Эти проверки не исправляют ACL.

Отдельно approved effective-access средством/Windows Advanced Security Effective Access и разбором applies-to/групп проверить права реальных посторонних tokens: direct/indirect memberships, Deny, inherit-only, CREATOR OWNER, OWNER RIGHTS, наследование. Простое OR allow-ACE или Get-Acl не вычисляет effective access. Не менять групповые memberships, привилегии или политики. Не проводить атакующие create/delete пробы в ProgramData. Если средство или полный membership scope недоступны — BLOCKED.

На bootstrap допустимо постороннее CreateDirectories при подтверждённой модели без concurrent precreation; недопустимы эффективные DeleteChild, изменение owner/DACL, подмена самого ProgramData/предков. Отдельно оценить parent DELETE через права C:\ и привилегированные tokens. На будущем новом parent — только три approved SID, owner CURRENT_USER, никаких inherited ACE. После создания повторить независимый read-only review. Если есть конфликт с endpoint policy — STOP, без обхода.

Сохранить private reviewer receipt: точный source/tool baseline reference, время, scope/effective-rights decision, отсутствующие доказательства и trust/concurrency assumptions. Не выводить SID/path/ACL/hostname/raw errors в public artifact. Нельзя выводить полный Get-Acl в GitHub/чат.

## Шаг A — подготовка функций, без изменения ACL

Утверждения по умолчанию false. Переводить в true только после описанного реального review; это не автоматическая аттестация. Следующий код не выполнять физически без отдельного решения оператора.

```powershell
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
$Parent = 'C:\ProgramData'
$ParentIndependentlyReviewed = $false # true только после реального отдельного review
$TrustedWritersQuiescent = $false    # true только при исключённых concurrent writers
$me = [Security.Principal.WindowsIdentity]::GetCurrent().User
$allowed = @($me.Value, 'S-1-5-18', 'S-1-5-32-544') | Select-Object -Unique

function Assert-LocalChain([string]$Path) {
    if ($Path -notmatch '^[A-Za-z]:\\' -or $Path.Substring(2).Contains(':') -or
        $Path -match '[<>"|?*]' -or $Path -match '(^|\\)\.\.?($|\\)' -or
        $Path -match '[ .]($|\\)') { throw 'NAMESPACE_BLOCKED' }
    $full = [IO.Path]::GetFullPath($Path)
    $node = [IO.DirectoryInfo]::new($full)
    while ($null -ne $node) {
        $node.Refresh()
        if (-not $node.Exists -or
            ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'NAMESPACE_BLOCKED'
        }
        $node = $node.Parent
    }
    return $full
}

function Assert-PrivateDirectory([string]$Path) {
    $null = Assert-LocalChain $Path
    $di = [IO.DirectoryInfo]::new($Path)
    $acl = $di.GetAccessControl()
    if (-not $acl.AreAccessRulesProtected -or -not $acl.AreAccessRulesCanonical -or
        $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $me.Value) {
        throw 'PRIVATE_ACL_BLOCKED'
    }
    $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne $allowed.Count) { throw 'PRIVATE_ACL_BLOCKED' }
    foreach ($sid in $allowed) {
        $r = @($rules | Where-Object { $_.IdentityReference.Value -eq $sid })
        if ($r.Count -ne 1) { throw 'PRIVATE_ACL_BLOCKED' }
        if ($r[0].IsInherited -or $r[0].AccessControlType -ne 'Allow' -or
            $r[0].FileSystemRights -ne [Security.AccessControl.FileSystemRights]::FullControl -or
            $r[0].InheritanceFlags -ne ([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
                [Security.AccessControl.InheritanceFlags]::ObjectInherit) -or
            $r[0].PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None) {
            throw 'PRIVATE_ACL_BLOCKED'
        }
    }
}
```

## Шаг B — единственное создание нового parent (не read-only)

Ни один существующий ACL не меняется. Нет Set-Acl, /reset, /grant, recursive traversal или удаления. Create с готовой DirectorySecurity применяется только к случайному новому имени. Если имя уже существует — STOP без попытки «починить», даже при внешне подходящем ACL. Случай между Test-Path и Create остаётся причиной ограничения threat model.

```powershell
try {
    if ($PSVersionTable.PSVersion.Major -ne 5 -or
        $PSVersionTable.PSVersion.Minor -ne 1 -or -not [Environment]::Is64BitProcess -or
        -not $ParentIndependentlyReviewed -or -not $TrustedWritersQuiescent) {
        throw 'PRECONDITION_BLOCKED'
    }
    $Parent = Assert-LocalChain $Parent
    $NewPrivate = [IO.Path]::Combine($Parent, 'MetaAnalyse-G0-Private-' + [Guid]::NewGuid().ToString('N'))
    if (Test-Path -LiteralPath $NewPrivate) { throw 'COLLISION_BLOCKED' }
    $security = [Security.AccessControl.DirectorySecurity]::new()
    $security.SetAccessRuleProtection($true, $false)
    $security.SetOwner($me)
    foreach ($sidText in $allowed) {
        $sid = [Security.Principal.SecurityIdentifier]::new($sidText)
        $rule = [Security.AccessControl.FileSystemAccessRule]::new(
            $sid, [Security.AccessControl.FileSystemRights]::FullControl,
            ([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
             [Security.AccessControl.InheritanceFlags]::ObjectInherit),
            [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow)
        $security.AddAccessRule($rule)
    }
    $newInfo = [IO.DirectoryInfo]::new($NewPrivate)
    $newInfo.Create($security)
    Assert-PrivateDirectory $NewPrivate
    if (@($newInfo.GetFileSystemInfos()).Count -ne 0) { throw 'NONEMPTY_BLOCKED' }
    'NEW_NAMESPACE_CHECKED_OBSERVER_NOT_AUTHORIZED'
} catch { 'BLOCKED_NEW_NAMESPACE'; } # STOP; retain any partial/new directory; no automatic retry
```

При любом BLOCKED немедленно остановить весь сеанс; не выполнять шаг C, не повторять с другим именем автоматически. Catch не выполняет rollback. Возможный пустой/частично созданный каталог оставить приватно, не удалять по pathname. Успешная строка НЕ даёт права запускать observer.

## Шаг C — независимый read-only review нового parent

Reviewer повторно выполняет функции проверки и effective-access review: owner CURRENT_USER, ровно три уникальных SID, protected/canonical DACL, только explicit Allow FullControl с ContainerInherit/ObjectInherit; directory пуст; вся цепочка non-reparse и не изменилась. Фактическое имя parent сопоставляется с приватной записью шага B. Согласованный ACL не доказывает происхождение объекта при malicious race. Доказательства такого race или отсутствие уверенности => STOP.

```powershell
try {
    if (-not $ParentIndependentlyReviewed -or -not $TrustedWritersQuiescent) {
        throw 'PRECONDITION_BLOCKED'
    }
    Assert-PrivateDirectory $NewPrivate
    if (@([IO.DirectoryInfo]::new($NewPrivate).GetFileSystemInfos()).Count -ne 0) {
        throw 'NONEMPTY_BLOCKED'
    }
    $FutureOutput = [IO.Path]::Combine($NewPrivate, 'http-format-' + [Guid]::NewGuid().ToString('N') + '.json')
    if (Test-Path -LiteralPath $FutureOutput) { throw 'COLLISION_BLOCKED' }
    'NAMESPACE_PREFLIGHT_CHECKED_G0_FAIL_CLOSED'
} catch { 'BLOCKED_NAMESPACE_PREFLIGHT'; } # STOP, no observer
```

FutureOutput лишь зарезервирован в плане, файл этим шагом не создаётся. Не передавать его observer автоматически. После будущей любой записи каталог уже непустой: этот начальный preflight не применяют повторно к старому evidence-каталогу.

## NewOutput и завершение

PR60 `NewOutput` использует `x+b`: existing file/hardlink/symlink collision не должен превращаться в overwrite. Но ancestor reparse и hostile rename этим кодом не исключаются; held handle не гарантирует, что consumer потом откроет тот же объект по имени. Внутри одобренного нового parent посторонние уже не имеют CreateDirectories/Write/DeleteChild; это отличается от допуска sibling creation в ProgramData.

Write/flush без атомарной публикации/fsync не доказывают crash durability. Возможны пустой/частичный JSON, а также полный файл при ошибке/неизвестном exit. Любое неполное или неоднозначное evidence => FAIL_CLOSED, не PASS. Для дальнейшей операции необходим отдельный operator review точной schema/source/tree/session/status. Наличие файла, порт 17845 и /ping не подтверждают ownership.

Cleanup: в данном runbook НИЧЕГО не удалять, не обнулять, не переименовывать. Старые ACL/evidence неизменны. Никаких Remove-Item -Recurse, wildcard, erase или восстановления ACL по сохранённому pathname. Позднейший cleanup — отдельная review-процедура с identity/ownership/link проверкой; пока сохранять reservation.

### Фиксированные stop conditions

STOP при: неподтверждённой provenance; не PS5.1 x64; необходимости Bypass/Unblock/Add-Type; неизвестном owner/effective access; untrusted DeleteChild/rename/WriteDac/WriteOwner; неподтверждённом NTFS/drive mapping; reparse; изменении цепочки; допустимом malicious precreator/concurrent writer; collision; ACL/owner mismatch; непустом новом parent; любой ошибке/частичной операции; утечке raw/private данных; конфликте политики. Никаких автоматических retries, observers, G1 или ремонта системы.

Итог на предоставленных наблюдениях: **BLOCKED до независимого review ProgramData/предков и bootstrap concurrency**. Предложение нового parent подготовлено; физическое создание и HTTP.sys observer NOT RUN. G0 FAIL_CLOSED / authorization NONE, G1 NO-GO.

Источники: [DirectoryInfo.Create(DirectorySecurity): security при создании и no-op при collision](https://learn.microsoft.com/en-us/dotnet/api/system.io.directoryinfo.create?view=netframework-4.7.2); [права FILE_ADD_SUBDIRECTORY/FILE_DELETE_CHILD](https://learn.microsoft.com/windows/win32/wmisdk/file-and-directory-access-rights-constants); [Windows security descriptors и наследование](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights). Это API/source-анализ, не физическая аттестация.
