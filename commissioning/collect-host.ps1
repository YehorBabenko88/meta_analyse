[CmdletBinding(DefaultParameterSetName='Observe')]
param([Parameter(Mandatory=$true)][string]$Output,
      [Parameter(Mandatory=$true,ParameterSetName='Observe')][string]$PrivateObservation,
      [Parameter(Mandatory=$true,ParameterSetName='Aggregate')][switch]$AggregateReasons,
      [Parameter(Mandatory=$true)][string]$ExpectedSha,
      [string]$Manifest,
      [string]$ManifestSha256)
$ErrorActionPreference='Stop'
# Observation only: no authorization, services/configuration changes or app start.
$mode=if($AggregateReasons){'diagnose-aggregate'}else{'diagnose'}
$arguments=@('-3.12',(Join-Path $PSScriptRoot 'host_identity.py'),$mode,'--output',$Output,'--expected-sha',$ExpectedSha)
if(-not $AggregateReasons){$arguments+=@('--private-observation',$PrivateObservation)}
if($Manifest){$arguments+=@('--manifest',$Manifest)}
if($ManifestSha256){$arguments+=@('--manifest-sha256',$ManifestSha256)}
try {
    & py @arguments 2>$null
    $diagnosticExit=$LASTEXITCODE
} catch {
    '{"status":"FAIL_CLOSED","reason_codes":["PYTHON_LAUNCH_UNAVAILABLE"],"authorization":"NONE"}'
    exit 1
}
if ($diagnosticExit -ne 0) {
    [Console]::Error.WriteLine('Read-only inventory blocked; inspect diagnostic_status/reason_codes in the public report. No authorization created.')
    exit $diagnosticExit
}
