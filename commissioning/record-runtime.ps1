param(
  [Parameter(Mandatory=$true)][string]$ExpectedComputer,
  [Parameter(Mandatory=$true)][int]$AppProcessId,
  [Parameter(Mandatory=$true)][ValidateSet(30,120,1440)][int]$Minutes,
  [Parameter(Mandatory=$true)][string]$OutputDirectory,
  [Parameter(Mandatory=$true)][string]$CandidateSha
)
$ErrorActionPreference='Stop'
if ($env:COMPUTERNAME -ne $ExpectedComputer -or ($env:COMPUTERNAME -replace '-','') -in @('LS5','LS7')) { throw 'Wrong or protected computer' }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$watch=[System.Diagnostics.Stopwatch]::StartNew()
$completed=$false
try {
  while ($watch.Elapsed.TotalMinutes -lt $Minutes) {
    $process=Get-Process -Id $AppProcessId -ErrorAction Stop
    [ordered]@{utc=[datetime]::UtcNow.ToString('o');elapsed_seconds=$watch.Elapsed.TotalSeconds;candidate_sha=$CandidateSha;pid=$AppProcessId;cpu_seconds=$process.CPU;working_set_bytes=$process.WorkingSet64;private_bytes=$process.PrivateMemorySize64;handles=$process.HandleCount;threads=$process.Threads.Count} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $OutputDirectory 'resources.jsonl') -Encoding utf8
    Start-Sleep -Seconds 5
  }
  $completed=$true
} finally {
  [ordered]@{candidate_sha=$CandidateSha;requested_minutes=$Minutes;observed_seconds=$watch.Elapsed.TotalSeconds;observer_completed=$completed;application_health_verdict='NOT_EVALUATED'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDirectory 'observer-result.json') -Encoding utf8
}
