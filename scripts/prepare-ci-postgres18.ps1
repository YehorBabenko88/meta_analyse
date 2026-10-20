param([string]$WorkRoot = (Join-Path $env:RUNNER_TEMP 'meta-analyse-pg18'))
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'Disposable GitHub Windows runner required; no workstation installation' }
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$archive = Join-Path $WorkRoot 'postgresql-18.6-5.zip'
$url = 'https://get.enterprisedb.com/postgresql/postgresql-18.6-5-windows-x64-binaries.zip'
$expected = 'E2246BA91D22345BC3D017586C09EDE52D9DF180B1EEB480F050445F1CAD84E2'
Invoke-WebRequest $url -OutFile $archive
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) { throw 'PostgreSQL18 archive checksum mismatch' }
Expand-Archive -LiteralPath $archive -DestinationPath $WorkRoot
$bin = Join-Path $WorkRoot 'pgsql/bin'
$version = (& (Join-Path $bin 'postgres.exe') --version) -join ' '
if ($LASTEXITCODE -ne 0 -or $version -notmatch 'PostgreSQL\) 18\.6') { throw 'Pinned PostgreSQL18.6 binary required' }
[ordered]@{url=$url;sha256=$expected;binary_version=$version;scope='disposable GitHub runner only'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $WorkRoot 'provenance.json') -Encoding utf8
"pgbin=$bin" | Add-Content -LiteralPath $env:GITHUB_OUTPUT -Encoding utf8
