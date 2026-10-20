param([Parameter(Mandatory=$true)][string]$ExpectedComputer,[Parameter(Mandatory=$true)][switch]$OperatorApproved)
$ErrorActionPreference='Stop'
if (!$OperatorApproved -or $env:COMPUTERNAME -ne $ExpectedComputer -or ($env:COMPUTERNAME -replace '-','') -in @('LS5','LS7')) { throw 'Wrong or protected computer / approval missing' }
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
