[CmdletBinding()]
param(
    [string]$Python = 'python',
    [string]$PgBin = '',
    [string]$WorkRoot = (Join-Path $env:RUNNER_TEMP 'meta-analyse-ci')
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$WorkRoot = (Resolve-Path $WorkRoot).Path
if (-not $PgBin) {
    $installed = Get-ChildItem 'C:\Program Files\PostgreSQL' -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Where-Object { $_.Name -match '^18(\.|$)' -and (Test-Path (Join-Path $_.FullName 'bin\initdb.exe')) } | Select-Object -First 1
    if ($installed) { $PgBin = Join-Path $installed.FullName 'bin' }
}
if (-not $PgBin) {
    throw 'PostgreSQL 18 binaries are required for Windows CI; install PG18 on runner or provide -PgBin. Refusing legacy 17.6 fallback.'
}
$version = (& (Join-Path $PgBin 'postgres.exe') --version) -join ' '
Write-Host "Selected Windows PostgreSQL: $version"
if ($LASTEXITCODE -ne 0 -or $version -notmatch 'PostgreSQL\) 18\.') { throw "PostgreSQL 18 required; found: $version" }
$data = Join-Path $WorkRoot 'pgdata'
$log = Join-Path $WorkRoot 'postgresql.log'
# Reserve an available loopback port; no production database is used.
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = $listener.LocalEndpoint.Port
$listener.Stop()
& (Join-Path $PgBin 'initdb.exe') -D $data -U meta_audit --auth=trust --no-locale --encoding=UTF8
if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
$oldDsn = $env:META_ANALYSE_TEST_ADMIN_DSN
$oldTestDsn = $env:META_ANALYSE_TEST_DSN
$oldQt = $env:QT_QPA_PLATFORM
$started = $false
try {
    & (Join-Path $PgBin 'pg_ctl.exe') -D $data -l $log -o "-h 127.0.0.1 -p $port" -w start
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed' }
    $started = $true
    $env:META_ANALYSE_TEST_ADMIN_DSN = "host=127.0.0.1 port=$port user=meta_audit dbname=postgres"
    $env:META_ANALYSE_TEST_DSN = $env:META_ANALYSE_TEST_ADMIN_DSN
    $env:QT_QPA_PLATFORM = 'offscreen'
    & $Python -m compileall -q src
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed' }
    & $Python scripts/repeat_lifecycle_tests.py --runs 10 --output-dir (Join-Path $WorkRoot 'repeat-lifecycle')
    if ($LASTEXITCODE -ne 0) { throw 'Repeated lifecycle tests failed; see repeat-lifecycle logs' }
    & $Python -m pytest -q -W error::RuntimeWarning --junitxml (Join-Path $WorkRoot 'tests.xml') --basetemp (Join-Path $WorkRoot 'pytest-temp') 2>&1 | Tee-Object -FilePath (Join-Path $WorkRoot 'tests.log')
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; see tests.log and tests.xml' }
    & $Python scripts/check_integration_postgres.py (Join-Path $WorkRoot 'tests.xml')
    if ($LASTEXITCODE -ne 0) { throw 'Mandatory PostgreSQL/shutdown JUnit gate failed' }
} finally {
    if ($started) { & (Join-Path $PgBin 'pg_ctl.exe') -D $data -m fast -w stop }
    $env:META_ANALYSE_TEST_ADMIN_DSN = $oldDsn
    $env:META_ANALYSE_TEST_DSN = $oldTestDsn
    $env:QT_QPA_PLATFORM = $oldQt
}
