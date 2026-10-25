# Read-only ADMINIT G0 discovery. No services, ACL, registry, PostgreSQL or firewall changes.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedSha,
      [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedTree,
      [Parameter(Mandatory=$true)][string]$Repo)
$ErrorActionPreference='Stop'
try {
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
$head=$null
$tree=$null
$clean=$false
if(Test-Path -LiteralPath (Join-Path $Repo '.git')) {
    $head=(& git -C $Repo rev-parse HEAD).Trim()
    if($LASTEXITCODE -ne 0) { throw 'Git source identity unavailable' }
    $tree=(& git -C $Repo rev-parse 'HEAD^{tree}').Trim()
    if($LASTEXITCODE -ne 0) { throw 'Git tree identity unavailable' }
    $dirty=@(& git -C $Repo status --porcelain)
    if($LASTEXITCODE -ne 0) { throw 'Git worktree state unavailable' }
    $clean=($dirty.Count -eq 0)
}
$pg=Get-CimInstance Win32_Service -ErrorAction Stop | Where-Object { $_.Name -like 'postgresql*' } |
    ForEach-Object { [pscustomobject]@{Name=$_.Name;State=$_.State} }
$listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop |
    Where-Object { $_.LocalPort -in @(5432,55432,55480) } |
    Select-Object LocalAddress,LocalPort)
$meta=@(Get-Process -ErrorAction Stop | Where-Object {$_.ProcessName -eq 'MetaScalp'})
$port55480=@($listeners | Where-Object {$_.LocalPort -eq 55480}).Count
$verdict=if($head -ne $ExpectedSha) {'BLOCKED_SOURCE_SHA'} elseif($tree -ne $ExpectedTree) {'BLOCKED_SOURCE_TREE'} elseif(-not $clean) {'BLOCKED_DIRTY_WORKTREE'} elseif($port55480 -ne 0) {'BLOCKED_PORT_55480_IN_USE'} else {'OBSERVATION_ONLY'}
[pscustomobject]@{
    Status=$verdict
    Authorization='NONE'
    Elevated=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    ExpectedSha=$ExpectedSha
    ActualSha=$head
    ExpectedTree=$ExpectedTree
    ActualTree=$tree
    WorktreeClean=$clean
    PostgreSQLServices=$pg
    PostgreSQLListeners=$listeners
    MetaScalpProcessCount=@($meta).Count
    PrivateTestPort55480Free=($port55480 -eq 0)
    Note='Read-only observations; not complete process inventory or host authorization'
} | ConvertTo-Json -Depth 5
if($verdict -ne 'OBSERVATION_ONLY'){exit 1}
} catch {
    # Never echo native errors, private paths or raw observations on refusal.
    '{"Status":"BLOCKED_DISCOVERY","Authorization":"NONE"}'
    exit 1
}
