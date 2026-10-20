param([string]$ServiceName='postgresql-x64-18',
      [Parameter(Mandatory=$true)][string]$Output,[switch]$CheckReadiness)
$ErrorActionPreference='Stop'
$service=Get-CimInstance Win32_Service -Filter "Name='$ServiceName'"
if (-not $service) { throw 'PostgreSQL service not found' }
$match=[regex]::Match($service.PathName,'(?i)-D\s+(?:"([^"]+)"|(\S+))')
if (-not $match.Success) { throw 'Service data directory cannot be established' }
$data=if($match.Groups[1].Success){$match.Groups[1].Value}else{$match.Groups[2].Value}
$binaryMatch=[regex]::Match($service.PathName,'^"([^"]+)"')
if (-not $binaryMatch.Success) { throw 'Service binary path cannot be established' }
$bin=Split-Path $binaryMatch.Groups[1].Value -Parent
$pidFile=Join-Path $data 'postmaster.pid'
$lines=Get-Content -LiteralPath $pidFile
$postmasterId=[int]$lines[0];$port=[int]$lines[3]
$process=Get-CimInstance Win32_Process -Filter "ProcessId=$postmasterId"
if ($process.Name -ne 'postgres.exe') { throw 'Postmaster identity mismatch' }
$bindings=@(Get-NetTCPConnection -State Listen | Where-Object OwningProcess -eq $postmasterId | Select-Object LocalAddress,LocalPort)
$configuredPort=(& (Join-Path $bin 'postgres.exe') -D $data -C port 2>$null) -join ''
$portQueryExit=$LASTEXITCODE
$configuredListen=(& (Join-Path $bin 'postgres.exe') -D $data -C listen_addresses 2>$null) -join ''
$listenQueryExit=$LASTEXITCODE
$version=(& (Join-Path $bin 'postgres.exe') --version) -join ''
$ready='NOT_RUN'
if ($CheckReadiness) {
    if (Get-ChildItem Env: | Where-Object { $_.Name -like 'PG*' -and $_.Value }) { throw 'Implicit PostgreSQL environment must be reviewed before readiness probe' }
    & (Join-Path $bin 'pg_isready.exe') -h 127.0.0.1 -p $port -t 3 | Out-Null
    $ready=if($LASTEXITCODE -eq 0){'ACCEPTING_NOT_AUTHENTICATED'}else{'NOT_ACCEPTING'}
}
[ordered]@{observed_utc=[datetime]::UtcNow.ToString('o');service=$ServiceName;service_state=$service.State;
 binary_version=$version;data_directory=$data;pid_file_port=$port;pid_file_state=$lines[-1];
 config_port=if($portQueryExit -eq 0){$configuredPort}else{'UNVERIFIED'};
 config_listen_addresses=if($listenQueryExit -eq 0){$configuredListen}else{'UNVERIFIED'};
 actual_bindings=$bindings;readiness=$ready;authentication='NOT_RUN';database_role_isolation='UNVERIFIED';
 configuration_changed=$false} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Output -Encoding utf8
Write-Host 'Read-only PostgreSQL discovery saved; readiness does not establish authentication/isolation.'
