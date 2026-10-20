param([Parameter(Mandatory=$true)][string]$ExpectedComputer,[Parameter(Mandatory=$true)][switch]$OperatorApproved,
      [Parameter(Mandatory=$true)][string]$Enrollment,[Parameter(Mandatory=$true)][string]$Manifest,
      [Parameter(Mandatory=$true)][string]$ExpectedSha,[Parameter(Mandatory=$true)][string]$ManifestSha256)
$ErrorActionPreference='Stop'
if (!$OperatorApproved) { throw 'Operator approval missing' }
& py -3.12 (Join-Path $PSScriptRoot 'host_identity.py') check --enrollment $Enrollment --manifest $Manifest --expected-sha $ExpectedSha --manifest-sha256 $ManifestSha256 --expected-computer $ExpectedComputer
if ($LASTEXITCODE -ne 0) { throw 'Specific host/source/Grid authorization failed; no environment changes made' }
$root=Split-Path $PSScriptRoot -Parent
& py -3.12 -m venv (Join-Path $root '.venv')
if ($LASTEXITCODE -ne 0) { throw 'Python3.12 venv failed' }
$python=Join-Path $root '.venv/Scripts/python.exe'
Push-Location $root
try {
  & $python -m pip install -c requirements.lock -e '.[test,archive]'
  if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed' }
  & $python -m pip check
  if ($LASTEXITCODE -ne 0) { throw 'Dependency validation failed' }
} finally { Pop-Location }
