# Read-only internal collector. stdout contains private identity inputs for the
# capturing Python process; never redirect/publish this raw stream to GitHub.
$ErrorActionPreference = 'Stop'
$tokenIdentity=[Security.Principal.WindowsIdentity]::GetCurrent()
$collectorElevated=([Security.Principal.WindowsPrincipal]::new($tokenIdentity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $collectorElevated) { throw 'ELEVATED_TOKEN_REQUIRED' }
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$errorsFound = [System.Collections.Generic.List[string]]::new()
$findings = [System.Collections.Generic.List[string]]::new()
$metascalp = [System.Collections.Generic.List[object]]::new()
$listeners = @()
$processes = @()
$services = @()
$tasks = @()
try { $os = Get-CimInstance Win32_OperatingSystem; $hardware = Get-CimInstance Win32_ComputerSystemProduct } catch { $errorsFound.Add('OS/hardware inventory unavailable') }
try { $current = [System.Security.Principal.WindowsIdentity]::GetCurrent(); $version = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'; $machine = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Cryptography' } catch { $errorsFound.Add('Windows installation/user inventory unavailable') }
try { $services = @(Get-CimInstance Win32_Service) } catch { $errorsFound.Add('Service inventory unavailable') }
try { $tasks = @(Get-ScheduledTask) } catch { $errorsFound.Add('Scheduled task inventory unavailable') }
try { $processes = @(Get-CimInstance Win32_Process) } catch { $errorsFound.Add('Process inventory unavailable') }
try { $listeners = @(Get-NetTCPConnection -State Listen) } catch { $errorsFound.Add('TCP inventory unavailable') }

foreach ($service in $services) {
    if (($service.Name + ' ' + $service.DisplayName + ' ' + $service.PathName) -match '(?i)bybit.?cluster|bybit.?grid|cluster.?grid|\\grid\\') { $findings.Add('Grid service footprint') }
}
foreach ($task in $tasks) {
    # This one system task is explicitly accounted for, rather than excluding
    # every task under Microsoft\Windows from inspection.
    if ($task.TaskPath -eq '\Microsoft\Windows\Sustainability\' -and $task.TaskName -eq 'PowerGridForecastTask') { continue }
    $taskText=$task.TaskName + ' ' + $task.TaskPath + ' ' + (($task.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -join ' ')
    if ($taskText -match '(?i)grid' -or ($task.TaskPath -notlike '\Microsoft\Windows\*' -and $taskText -match '(?i)coordinator|collector|worker')) { $findings.Add('Grid or conflicting scheduled task') }
}
$processEvidence = @()
try { . (Join-Path $PSScriptRoot 'process-evidence.ps1') } catch { $errorsFound.Add('Native process identity collector unavailable') }
foreach ($process in $processes) {
    if (-not $process.ExecutablePath) {
        try { $processEvidence += Get-MissingProcessEvidence -ProcessRecord $process }
        catch { $processEvidence += [ordered]@{process=[ordered]@{pid=[int]$process.ProcessId;name=$process.Name};evidence=@{collection_error='PROCESS_EVIDENCE_UNAVAILABLE'}} }
    }
    if (($process.Name + ' ' + $process.ExecutablePath) -match '(?i)bybit.?cluster|bybit.?grid|cluster.?grid|\\grid\\|^(coordinator|worker|collector)(\.exe)? ') { $findings.Add('Grid or conflicting runtime process') }
}
$homePath = [Environment]::GetFolderPath('UserProfile')
$gridRoots = @(
    (Join-Path ([Environment]::GetFolderPath('ProgramFiles')) 'BybitClusterGrid'),
    (Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'BybitClusterGrid'),
    (Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'BybitGridCommissioning'),
    (Join-Path $homePath 'GridCommissioning'), (Join-Path $homePath 'BybitClusterGrid')
)
foreach ($root in $gridRoots) {
    try { if (Test-Path -LiteralPath $root -ErrorAction Stop) { $findings.Add('Grid directory footprint'); Get-Item -LiteralPath $root -ErrorAction Stop | Out-Null } } catch { $errorsFound.Add('Grid path inventory unavailable') }
}
$credentialNames = [System.Collections.Generic.List[string]]::new()
$dsnNames = [System.Collections.Generic.List[string]]::new()
foreach ($scope in @('Process','User','Machine')) {
    try {
        $variables = [Environment]::GetEnvironmentVariables($scope)
        foreach ($key in $variables.Keys) {
            if (-not $variables[$key]) { continue }
            if ($key -match '(?i)^(API_KEY|API_SECRET)$|(?:BYBIT|BINANCE|OKX|KUCOIN|COINBASE|EXCHANGE).*(?:KEY|SECRET|TOKEN)') { $credentialNames.Add("${scope}:$key") }
            if ($key -ne 'META_ANALYSE_COMMISSIONING_DSN' -and ($key -match '(?i)DSN|DATABASE_URL|GRID.*(?:DATABASE|DB_|PG)|^PG(?:HOST|PORT|DATABASE|USER|PASSWORD|SERVICE|OPTIONS|PASSFILE|SSLMODE)' -or [string]$variables[$key] -match '(?i)^postgres(?:ql)?://|(?:^|\s)(?:host|dbname|user|password)=')) { $dsnNames.Add("${scope}:$key") }
        }
    } catch { $errorsFound.Add('Environment-name inventory unavailable') }
}

# Only bounded known install roots and registry metadata; no drive-wide crawl.
$candidatePaths = [System.Collections.Generic.List[string]]::new()
foreach ($registry in @('HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*')) {
    foreach ($item in @(Get-ItemProperty $registry -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match '(?i)MetaScalp' })) {
        if ($item.DisplayIcon) { $candidatePaths.Add(($item.DisplayIcon -replace ',\d+$','').Trim('"')) }
        if ($item.InstallLocation -and (Test-Path -LiteralPath $item.InstallLocation)) { Get-ChildItem -LiteralPath $item.InstallLocation -Filter '*MetaScalp*.exe' -File -ErrorAction SilentlyContinue | ForEach-Object { $candidatePaths.Add($_.FullName) } }
    }
}
foreach ($root in @((Join-Path ([Environment]::GetFolderPath('ProgramFiles')) 'MetaScalp'),(Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'MetaScalp'),(Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Programs/MetaScalp'))) {
    if (Test-Path -LiteralPath $root) { Get-ChildItem -LiteralPath $root -Filter '*MetaScalp*.exe' -File -Recurse -Depth 3 -ErrorAction SilentlyContinue | ForEach-Object { $candidatePaths.Add($_.FullName) } }
}
foreach ($path in @($candidatePaths | Select-Object -Unique)) {
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $file = Get-Item -LiteralPath $path
        try {
            $signature = Get-AuthenticodeSignature -LiteralPath $path
            $metascalp.Add([ordered]@{path=$path;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant();file_version=$file.VersionInfo.FileVersion;signature=$signature.Status.ToString();publisher=$signature.SignerCertificate.Subject})
        } catch { $errorsFound.Add('MetaScalp signature/hash verification unavailable') }
    }
}
$postgresListeners = @()
$apiListeners = @()
foreach ($listener in $listeners) {
    $process = $processes | Where-Object ProcessId -eq $listener.OwningProcess | Select-Object -First 1
    if ($process.Name -ieq 'postgres.exe') {
        $dataPath = ''
        if ($process.CommandLine -match '(?:^|\s)-D\s+(?:"([^"]+)"|(\S+))') { if ($Matches[1]) { $dataPath=$Matches[1] } else { $dataPath=$Matches[2] } }
        $postgresListeners += [ordered]@{port=[int]$listener.LocalPort;address=$listener.LocalAddress;data_directory=$dataPath}
    }
    if ($listener.LocalPort -ge 17845 -and $listener.LocalPort -le 17855 -and $process.ExecutablePath) {
        try { $apiListeners += [ordered]@{port=[int]$listener.LocalPort;address=$listener.LocalAddress;exe_sha256=(Get-FileHash -LiteralPath $process.ExecutablePath -Algorithm SHA256).Hash.ToLowerInvariant()} } catch { $errorsFound.Add('API process identity unavailable') }
    }
}
$httpSysState = (& netsh.exe http show servicestate view=requestq verbose=yes) -join "`n"
if ($LASTEXITCODE -ne 0) { $errorsFound.Add('HTTP.sys queue inventory unavailable') }
$terminalProcesses = @($processes | Where-Object { $_.Name -ieq 'MetaScalp.exe' } | ForEach-Object {
    if (-not $_.ExecutablePath -or -not $_.CreationDate) { $errorsFound.Add('MetaScalp process identity incomplete') }
    else { [ordered]@{pid=[int]$_.ProcessId;process_started=$_.CreationDate.ToUniversalTime().ToString('o');exe_path=$_.ExecutablePath;exe_sha256=(Get-FileHash -LiteralPath $_.ExecutablePath -Algorithm SHA256).Hash.ToLowerInvariant()} }
})
[ordered]@{
    collector_elevated=$collectorElevated
    process_evidence=@($processEvidence)
    process_roots=[ordered]@{system32=[Environment]::SystemDirectory;program_files=[Environment]::GetFolderPath('ProgramFiles')}
    private_inventory=[ordered]@{
        scope='All visible processes, services, scheduled tasks and TCP listeners; bounded known Grid directories, install metadata and environment names. No drive-wide absence claim.'
        services=@($services | Select-Object Name,DisplayName,State,PathName,StartName)
        processes=@($processes | Select-Object Name,ProcessId,ParentProcessId,SessionId,ExecutablePath,@{Name='CreationDate';Expression={if($_.CreationDate){$_.CreationDate.ToUniversalTime().ToString('o')}else{$null}}},@{Name='CreationFileTime';Expression={if($_.CreationDate){$_.CreationDate.ToUniversalTime().ToFileTimeUtc()}elseif($_.ProcessId -eq 0){0}else{$null}}})
        tasks=@($tasks | Select-Object TaskPath,TaskName,State,@{Name='Actions';Expression={@($_.Actions | Select-Object Execute,Arguments,ClassId)}})
        listeners=@($listeners | Select-Object LocalAddress,LocalPort,OwningProcess)
        checked_grid_roots=$gridRoots
        excluded_system_task='\Microsoft\Windows\Sustainability\PowerGridForecastTask'
    }
    http_sys_state=$httpSysState;terminal_processes=$terminalProcesses
    identity=[ordered]@{hostname=[System.Net.Dns]::GetHostName();username=$current.Name;sid=$current.User.Value;machine_guid=$machine.MachineGuid;install_id=[string]$version.InstallDate;hardware_uuid=$hardware.UUID}
    os=[ordered]@{system='Windows';edition=$version.EditionID;build=[int]$version.CurrentBuildNumber}
    grid=[ordered]@{findings=@($findings);errors=@($errorsFound);coverage_complete=($errorsFound.Count -eq 0);visible_services=$services.Count;visible_tasks=$tasks.Count;visible_processes=$processes.Count}
    credential_names=@($credentialNames);production_dsn_names=@($dsnNames)
    postgres_listeners=@($postgresListeners);metascalp=@($metascalp);api_listeners=@($apiListeners)
    api_listening_ports=@($listeners | Where-Object { $_.LocalPort -ge 17845 -and $_.LocalPort -le 17855 -and $_.LocalAddress -in @('127.0.0.1','::1','0.0.0.0','::') } | ForEach-Object {[int]$_.LocalPort} | Select-Object -Unique)
} | ConvertTo-Json -Depth 8 -Compress
