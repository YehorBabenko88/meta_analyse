# Read-only ADMINIT G0 discovery. No services, ACL, registry, PostgreSQL or firewall changes.
[CmdletBinding()]
param([string]$ExpectedSha='6d01bf3d9f4118ac336624c9986c4ed876edd445',
      [string]$Repo='C:\MetaAnalyse-Test\git-pr13')
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
$head=$null
$clean=$false
if(Test-Path -LiteralPath (Join-Path $Repo '.git')) {
    $head=(& git -C $Repo rev-parse HEAD).Trim()
    if($LASTEXITCODE -ne 0) { throw 'Git source identity unavailable' }
    $dirty=@(& git -C $Repo status --porcelain)
    if($LASTEXITCODE -ne 0) { throw 'Git worktree state unavailable' }
    $clean=($dirty.Count -eq 0)
}
$pg=Get-CimInstance Win32_Service | Where-Object { $_.Name -like 'postgresql*' } |
    ForEach-Object { [pscustomobject]@{Name=$_.Name;State=$_.State} }
$listeners=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in @(5432,55432,55480) } |
    Select-Object LocalAddress,LocalPort)
$meta=Get-Process MetaScalp -ErrorAction SilentlyContinue
$port55480=@(Get-NetTCPConnection -LocalPort 55480 -State Listen -ErrorAction SilentlyContinue).Count
$verdict=if($head -ne $ExpectedSha) {'BLOCKED_SOURCE_SHA'} elseif(-not $clean) {'BLOCKED_DIRTY_WORKTREE'} elseif($port55480 -ne 0) {'BLOCKED_PORT_55480_IN_USE'} else {'OBSERVATION_ONLY'}
[pscustomobject]@{
    Status=$verdict
    Authorization='NONE'
    Elevated=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    ExpectedSha=$ExpectedSha
    ActualSha=$head
    WorktreeClean=$clean
    PostgreSQLServices=$pg
    PostgreSQLListeners=$listeners
    MetaScalpProcessCount=@($meta).Count
    PrivateTestPort55480Free=($port55480 -eq 0)
    Note='Read-only observations; not complete process inventory or host authorization'
} | ConvertTo-Json -Depth 5
if($verdict -ne 'OBSERVATION_ONLY'){exit 1}
