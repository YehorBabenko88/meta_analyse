# Creates only a NEW, manually operated cluster. Never installs a service.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Python,
 [Parameter(Mandatory=$true)][string]$Manifest,
 [Parameter(Mandatory=$true)][string]$ManifestSha256,
 [Parameter(Mandatory=$true)][string]$ExpectedSha,
 [Parameter(Mandatory=$true)][string]$Enrollment,
 [Parameter(Mandatory=$true)][string]$DataDirectory,
 [Parameter(Mandatory=$true)][string]$SessionName,
 [Parameter(Mandatory=$true)][switch]$OperatorApproved,
 [string]$PgBin='C:\Program Files\PostgreSQL\18\bin'
)
$ErrorActionPreference='Stop'
if (!$OperatorApproved) { throw 'Explicit approval required' }
if ($env:COMPUTERNAME -ine 'ADMINIT-JQ1IQSV' -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'ADMINIT-JQ1IQSV\Administrator') { throw 'Wrong host/user' }
if ($SessionName -cnotmatch '^meta_commission_[a-z0-9_]+$' -or $SessionName -eq 'meta_commission_bootstrap') { throw 'Invalid dedicated session role/database' }
if (Get-ChildItem Env: | Where-Object { $_.Name -like 'PG*' -and $_.Value }) { throw 'Implicit PG environment forbidden' }
$root=Split-Path $PSScriptRoot -Parent
& $Python (Join-Path $PSScriptRoot 'host_identity.py') check --enrollment $Enrollment --manifest $Manifest --expected-sha $ExpectedSha --manifest-sha256 $ManifestSha256 --expected-computer ADMINIT-JQ1IQSV
if ($LASTEXITCODE -ne 0) { throw 'Fresh host/source/inventory authorization failed' }
# Confirm requested creation path and role agree with the encrypted authorization.
$check=@'
import sys,ntpath
sys.path.insert(0,sys.argv[1])
from host_identity import load_private
p=load_private(sys.argv[2])['database']
assert ntpath.normcase(ntpath.normpath(p['data_directory']))==ntpath.normcase(ntpath.normpath(sys.argv[3]))
assert p['port']==55480 and p['dbname']==p['user']==sys.argv[4]
'@
& $Python -c $check $PSScriptRoot $Enrollment $DataDirectory $SessionName
if ($LASTEXITCODE -ne 0) { throw 'Encrypted database binding mismatch' }
$version=(& (Join-Path $PgBin 'postgres.exe') --version) -join ' '
if ($LASTEXITCODE -ne 0 -or $version -notmatch 'PostgreSQL\) 18\.1$') { throw 'Exact PostgreSQL 18.1 binaries required' }
$allowed=[IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'MetaAnalyseCommissioning'))
$data=[IO.Path]::GetFullPath($DataDirectory)
if (![IO.Path]::IsPathRooted($DataDirectory) -or !$data.StartsWith($allowed+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'New cluster must be beneath LocalAppData\MetaAnalyseCommissioning' }
if (Test-Path -LiteralPath $data) { throw 'Data directory already exists; never reuse or overwrite' }
$parent=Split-Path $data -Parent
$probe=$parent
while ($probe) {
 if ((Test-Path -LiteralPath $probe) -and ((Get-Item -LiteralPath $probe -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Reparse-point ancestor refused' }
 $probe=Split-Path $probe -Parent
}
$listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,55480)
try { $listener.Start() } finally { $listener.Stop() }
New-Item -ItemType Directory -Path $parent -Force | Out-Null
# Password is entered directly into initdb. No password in argv, env or transcript.
& (Join-Path $PgBin 'initdb.exe') -D $data -U meta_commission_bootstrap --auth=scram-sha-256 --encoding=UTF8 --no-locale -W
if ($LASTEXITCODE -ne 0) { throw 'initdb failed; partial NEW directory retained for review' }
Add-Content -LiteralPath (Join-Path $data 'postgresql.conf') -Encoding ascii -Value "`nlisten_addresses='127.0.0.1'`nport=55480`npassword_encryption='scram-sha-256'"
# No IPv6/wildcard or broad client network; no trust authentication.
Set-Content -LiteralPath (Join-Path $data 'pg_hba.conf') -Encoding ascii -Value 'host all all 127.0.0.1/32 scram-sha-256'
$started=$false
try {
 & (Join-Path $PgBin 'pg_ctl.exe') -D $data -l (Join-Path $parent 'postgresql.log') -w start
 if ($LASTEXITCODE -ne 0) { throw 'New private cluster startup failed' }
 $started=$true
 & (Join-Path $PgBin 'psql.exe') -X -W -h 127.0.0.1 -p 55480 -U meta_commission_bootstrap -d postgres -v "expected_data_directory=$($data.Replace('\','/'))" -v expected_port=55480 -v "test_db=$SessionName" -v "test_role=$SessionName" -f (Join-Path $PSScriptRoot 'create-test-db.sql')
 if ($LASTEXITCODE -ne 0) { throw 'New private role/database setup failed' }
 Write-Host "Set the session role password now (bootstrap password first, then a NEW role password):"
 & (Join-Path $PgBin 'psql.exe') -X -W -h 127.0.0.1 -p 55480 -U meta_commission_bootstrap -d postgres -c "\password $SessionName"
 if ($LASTEXITCODE -ne 0) { throw 'Session role password setup failed' }
} catch {
 if ($started) { & (Join-Path $PgBin 'pg_ctl.exe') -D $data -m fast -w stop | Out-Null }
 throw
}
Write-Host 'NEW private cluster prepared at 127.0.0.1:55480; existing services were not changed. No runtime test started.'
