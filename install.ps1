# User-level installer. Credentials are read from the launch environment only.
[CmdletBinding()]
param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'MetaAnalyse'),
    [string]$Python = ''
)
$ErrorActionPreference = 'Stop'

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments, [string]$Operation)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Operation failed (exit $LASTEXITCODE). Installation incomplete." }
}

$pythonCommand = $Python
$pythonArgs = @()
if (-not $pythonCommand) {
    $launcherCommand = Get-Command py -ErrorAction SilentlyContinue
    $has312 = $false
    if ($launcherCommand) {
        & py -3.12 -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))' 2>$null
        $has312 = ($LASTEXITCODE -eq 0)
    }
    if (-not $has312) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw 'Install Python 3.12, or specify -Python with its executable path.'
        }
        Invoke-Checked -Command 'winget' -Arguments @('install', '--id', 'Python.Python.3.12', '--exact', '--source', 'winget', '--accept-package-agreements', '--accept-source-agreements') -Operation 'Python installation'
        & py -3.12 -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))' 2>$null
        if ($LASTEXITCODE -ne 0) { throw 'Restart PowerShell after installing Python, then rerun install.ps1.' }
    }
    $pythonCommand = 'py'
    $pythonArgs = @('-3.12')
}
Invoke-Checked -Command $pythonCommand -Arguments ($pythonArgs + @('-c', 'import sys; sys.exit(sys.version_info[:2] != (3, 12))')) -Operation 'Python 3.12 verification'
$lock = Join-Path $PSScriptRoot 'requirements.lock'
if (-not (Test-Path -LiteralPath $lock)) { throw 'requirements.lock is missing; use a complete repository checkout.' }
New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
$venv = Join-Path $InstallRoot 'venv'
$exe = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    Invoke-Checked -Command $pythonCommand -Arguments ($pythonArgs + @('-m', 'venv', $venv)) -Operation 'Virtual environment creation'
}
Invoke-Checked -Command $exe -Arguments @('-c', 'import sys; sys.exit(sys.version_info[:2] != (3, 12))') -Operation 'Existing virtual environment verification'
Invoke-Checked -Command $exe -Arguments @('-m', 'pip', 'install', '--constraint', $lock, '-e', $PSScriptRoot) -Operation 'Dependency installation'
Invoke-Checked -Command $exe -Arguments @('-c', 'import meta_analyse.desktop') -Operation 'Application import verification'
$launcher = Join-Path $InstallRoot 'run.cmd'
# Preserve Unicode paths, quote spaces, escape cmd percent expansion.
$cmdExe = $exe.Replace('%', '%%')
$launcherText = "@echo off`r`nsetlocal DisableDelayedExpansion`r`nchcp 65001 >nul`r`n`"$cmdExe`" -m meta_analyse.desktop`r`n"
[System.IO.File]::WriteAllText($launcher, $launcherText, [System.Text.UTF8Encoding]::new($false))
Write-Host "Installed. Start: $launcher"
Write-Host 'Optional PostgreSQL connection: set environment META_ANALYSE_DSN (dedicated DB account)'
