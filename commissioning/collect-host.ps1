param([Parameter(Mandatory=$true)][string]$Output,
      [Parameter(Mandatory=$true)][string]$PrivateObservation,
      [Parameter(Mandatory=$true)][string]$ExpectedSha)
$ErrorActionPreference='Stop'
# Observation only: no authorization, services/configuration changes or app start.
& py -3.12 (Join-Path $PSScriptRoot 'host_identity.py') diagnose --output $Output --private-observation $PrivateObservation --expected-sha $ExpectedSha
$diagnosticExit=$LASTEXITCODE
if ($diagnosticExit -ne 0) {
    [Console]::Error.WriteLine('Read-only inventory blocked; inspect diagnostic_status/reason_codes in the public report. No authorization created.')
    exit $diagnosticExit
}
