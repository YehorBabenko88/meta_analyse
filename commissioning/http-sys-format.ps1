# PRIVATE internal stream for http_sys_format.py only. Never execute this file
# directly or redirect its raw stdout/stderr to a public file/transcript.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$netshPath = Join-Path ([Environment]::SystemDirectory) 'netsh.exe'
$privateLines = @(& $netshPath http show servicestate view=requestq verbose=yes)
$netshExit = $LASTEXITCODE
[ordered]@{schema=1;exit_code=$netshExit;text=($privateLines -join "`n")} | ConvertTo-Json -Depth 3 -Compress
