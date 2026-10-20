param([Parameter(Mandatory=$true)][string]$Output,
      [Parameter(Mandatory=$true)][string]$PrivateObservation)
$ErrorActionPreference='Stop'
# Observation only: no authorization, services/configuration changes or app start.
& py -3.12 (Join-Path $PSScriptRoot 'host_identity.py') diagnose --output $Output --private-observation $PrivateObservation
if ($LASTEXITCODE -ne 0) { throw 'Read-only identity observation failed; no authorization created' }
