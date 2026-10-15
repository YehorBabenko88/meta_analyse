# User-level installer. Review before running.
$ErrorActionPreference = 'Stop'
$Root = Join-Path $env:LOCALAPPDATA 'MetaAnalyse'
New-Item -ItemType Directory -Path $Root -Force | Out-Null
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Install Python 3.12 or winget first.' }
    winget install --id Python.Python.3.12 --exact --source winget --accept-package-agreements --accept-source-agreements
    $python = Get-Command py -ErrorAction SilentlyContinue
    if (-not $python) { throw 'Restart PowerShell after installing Python, then rerun install.ps1' }
}
& py -3.12 -m venv (Join-Path $Root 'venv')
$exe = Join-Path $Root 'venv\Scripts\python.exe'
& $exe -m pip install --upgrade pip
& $exe -m pip install -e $PSScriptRoot
$launcher = Join-Path $Root 'run.cmd'
"@echo off`r`n`"$exe`" -m meta_analyse.desktop" | Set-Content -Path $launcher -Encoding Ascii
Write-Host "Installed. Start: $launcher"
Write-Host 'Optional PostgreSQL connection: set environment META_ANALYSE_DSN (dedicated DB account)'
