param([Parameter(Mandatory=$true)][string]$PgBin)
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows') { throw 'Disposable hosted Windows runner required' }
$taskRoot=Join-Path $env:RUNNER_TEMP 'pr18-acceptance-pg'
New-Item -ItemType Directory -Force -Path $taskRoot | Out-Null
$data=Join-Path $taskRoot 'data'
$log=Join-Path $taskRoot 'postgresql.log'
$listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
$listener.Start();$port=$listener.LocalEndpoint.Port;$listener.Stop()
& (Join-Path $PgBin 'initdb.exe') -D $data -U acceptance --auth=trust --no-locale --encoding=UTF8
if($LASTEXITCODE -ne 0){throw 'Disposable initdb failed'}
$started=$false
try {
 & (Join-Path $PgBin 'pg_ctl.exe') -D $data -l $log -o "-h 127.0.0.1 -p $port" -w start
 if($LASTEXITCODE -ne 0){throw 'Disposable PostgreSQL start failed'}
 $started=$true
 $env:META_ANALYSE_TEST_ADMIN_DSN="host=127.0.0.1 port=$port user=acceptance dbname=postgres"
 $env:META_ANALYSE_TEST_DSN=$env:META_ANALYSE_TEST_ADMIN_DSN
 python -m compileall -q src commissioning scripts tests
 if($LASTEXITCODE -ne 0){throw 'Compilation failed'}
 python scripts/repeat_lifecycle_tests.py --runs 10 --output-dir (Join-Path $taskRoot 'repeat-lifecycle')
 if($LASTEXITCODE -ne 0){throw 'Lifecycle repetitions failed'}
 python ../acceptance-harness/acceptance/run.py full
 if($LASTEXITCODE -ne 0){throw 'Exact-source full suite failed'}
 python scripts/check_integration_postgres.py acceptance-raw.xml
 if($LASTEXITCODE -ne 0){throw 'Required PostgreSQL and shutdown identities failed'}
 python scripts/benchmark_flow_ui.py --seconds 3 --output (Join-Path $taskRoot 'ui-performance.json')
 if($LASTEXITCODE -ne 0){throw 'UI benchmark failed'}
 ./install.ps1 -Python (Get-Command python).Source -InstallRoot (Join-Path $taskRoot 'installer')
 if($LASTEXITCODE -ne 0){throw 'First installation failed'}
 ./install.ps1 -Python (Get-Command python).Source -InstallRoot (Join-Path $taskRoot 'installer')
 if($LASTEXITCODE -ne 0){throw 'Repeated installation failed'}
} finally {
 if($started){& (Join-Path $PgBin 'pg_ctl.exe') -D $data -m fast -w stop}
}
