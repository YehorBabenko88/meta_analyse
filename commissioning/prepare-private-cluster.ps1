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
if ($SessionName -cnotmatch '^meta_commission_[a-z0-9_]+$' -or $SessionName -eq 'meta_commission_bootstrap' -or $SessionName.Length -gt 63) { throw 'Invalid dedicated session role/database' }
if (Get-ChildItem Env: | Where-Object { $_.Name -like 'PG*' -and $_.Value }) { throw 'Implicit PG environment forbidden' }
$root=Split-Path $PSScriptRoot -Parent
& $Python (Join-Path $PSScriptRoot 'host_identity.py') check --enrollment $Enrollment --manifest $Manifest --expected-sha $ExpectedSha --manifest-sha256 $ManifestSha256 --expected-computer ADMINIT-JQ1IQSV
if ($LASTEXITCODE -ne 0) { throw 'Fresh host/source/inventory authorization failed' }
# Confirm requested creation path and role agree with the encrypted authorization.
$check=@'
import sys,ntpath
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from host_identity import load_private
p=load_private(sys.argv[2])['database']
if ntpath.normcase(ntpath.normpath(p['data_directory']))!=ntpath.normcase(ntpath.normpath(sys.argv[3])):
    raise ValueError('ENCRYPTED_DATABASE_BINDING_MISMATCH')
if not (type(p['port']) is int and p['port']==55480 and p['dbname']==p['user']==sys.argv[4]):
    raise ValueError('ENCRYPTED_DATABASE_BINDING_MISMATCH')
sys.path.insert(0,str(Path(sys.argv[1]).parent/'src'))
from meta_analyse.pg_cluster_plan import ClusterPlan,plan_only
plan_only(ClusterPlan(sys.argv[3],sys.argv[4],sys.argv[4]),localappdata=sys.argv[5])
'@
& $Python -c $check $PSScriptRoot $Enrollment $DataDirectory $SessionName $env:LOCALAPPDATA
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
# Read the newly created control file independently BEFORE any server is started.
# Never publish tool output: it contains private paths and cluster identity.
$previousLocale=$env:LC_ALL
try {
 $env:LC_ALL='C'
 $controlOutput=@(& (Join-Path $PgBin 'pg_controldata.exe') -D $data 2>&1)
 if ($LASTEXITCODE -ne 0) { throw 'FILE_CONTROL_IDENTITY_UNAVAILABLE' }
} catch { throw 'FILE_CONTROL_IDENTITY_UNAVAILABLE' }
finally { $env:LC_ALL=$previousLocale }
$systemIdLines=@($controlOutput | ForEach-Object { [string]$_ } | Where-Object { $_ -cmatch '^Database system identifier:\s+([1-9][0-9]{0,19})\s*$' })
if ($systemIdLines.Count -ne 1) { throw 'FILE_CONTROL_IDENTITY_AMBIGUOUS' }
$expectedSystemIdentifier=[regex]::Match($systemIdLines[0],'^Database system identifier:\s+([1-9][0-9]{0,19})\s*$').Groups[1].Value
[UInt64]$parsedSystemIdentifier=0
if (![UInt64]::TryParse($expectedSystemIdentifier,[ref]$parsedSystemIdentifier) -or $parsedSystemIdentifier -eq 0) { throw 'FILE_CONTROL_IDENTITY_INVALID' }
$controlOutput=$null
$systemIdLines=$null
Add-Content -LiteralPath (Join-Path $data 'postgresql.conf') -Encoding ascii -Value "`nlisten_addresses='127.0.0.1'`nport=55480`npassword_encryption='scram-sha-256'"
# No IPv6/wildcard or broad client network; no trust authentication.
Set-Content -LiteralPath (Join-Path $data 'pg_hba.conf') -Encoding ascii -Value 'host all all 127.0.0.1/32 scram-sha-256'
try {
 & (Join-Path $PgBin 'pg_ctl.exe') -D $data -l (Join-Path $data 'postgresql.log') -w start
 if ($LASTEXITCODE -ne 0) { throw 'New private cluster startup failed' }
 & (Join-Path $PgBin 'psql.exe') -X -W -h 127.0.0.1 -p 55480 -U meta_commission_bootstrap -d postgres -v "expected_data_directory=$($data.Replace('\','/'))" -v expected_port=55480 -v "expected_system_identifier=$expectedSystemIdentifier" -v "test_db=$SessionName" -v "test_role=$SessionName" -f (Join-Path $PSScriptRoot 'create-test-db.sql')
 if ($LASTEXITCODE -ne 0) { throw 'New private role/database setup failed' }
 Write-Host "Set the session role password now (bootstrap password first, then a NEW role password):"
 & (Join-Path $PgBin 'psql.exe') -X -W -h 127.0.0.1 -p 55480 -U meta_commission_bootstrap -d postgres -c "\password $SessionName"
 if ($LASTEXITCODE -ne 0) { throw 'Session role password setup failed' }
} catch {
 # A path/start exit code is not an ownership receipt. Startup timeout can
 # leave a live process; do not stop it without fresh physical ownership proof.
 Write-Warning 'Private cluster setup failed; retain NEW directory and process state for authorized ownership review. No automatic stop or deletion performed.'
 throw
}
Write-Host 'NEW private cluster prepared at 127.0.0.1:55480; existing services were not changed. No runtime test started.'
