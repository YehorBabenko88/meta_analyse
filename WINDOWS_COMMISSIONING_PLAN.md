# LS5-specific commissioning plan — 2026-10-20

**Current LS5 admission: NO-GO.** Grid footprints/incomplete inventory, private database isolation and inactive MetaScalp API remain blockers. Nothing below was executed as setup or smoke by the auditor. Read-only diagnostic reports were produced only. Green CI is not host clearance.

Code SHA: `5928b4e3aadac55d64bdd013c83ed698cfd8d838`.
Trusted CANDIDATE.json SHA256: `f444f345ccea8f5a263d9c9369518027f3abe76caa73a9e985a98ed30b693605`.
Source ZIP SHA256: `3ec9789521a38013f9df9a01b2c882a43a62c7648a16fb263608413b6a38696d`.

The generic LS5 name ban is replaced by private DPAPI CurrentUser authorization for the specified LS5/account plus installation/hardware/SID HMAC, exact source/digest, fresh Grid/environment evidence, approved software/API and dedicated cluster/role. LS7/other accounts are not supported by this enrollment procedure. No ignore-host switch exists.

## 0. Trust the package and use a private session

Use PowerShell under the specified Windows account, Python3.12 explicitly (not3.14). If elevated inventory is needed, use the same account; do not borrow another user's enrollment. Verify the outer ZIP against the independently published checksum before executing any script. Extract source.zip so source/ and CANDIDATE.json are siblings. Final reports here supersede historical reports inside frozen source.zip.

```powershell
$ErrorActionPreference='Stop'
$Session=Get-Date -Format 'yyyyMMdd_HHmmss'
$Packet='C:\Users\LS-5\MetaAnalyse-Commissioning\packet' # extracted verified packet
$Private=Join-Path $env:USERPROFILE "MetaAnalyse-Commissioning\Private\$Session"
New-Item -ItemType Directory -Path $Private | Out-Null
$Manifest=Join-Path $Packet 'CANDIDATE.json'
$Sha='5928b4e3aadac55d64bdd013c83ed698cfd8d838'
$ManifestHash='f444f345ccea8f5a263d9c9369518027f3abe76caa73a9e985a98ed30b693605'
if ((Get-FileHash -LiteralPath $Manifest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ManifestHash) { throw 'NO-GO: manifest mismatch' }
Set-Location (Join-Path $Packet 'source')
py -3.12 --version
if ($LASTEXITCODE -ne 0) { throw 'Python3.12 required' }
```

## 1. Read-only Grid/process/identity diagnostics — stop here on current LS5

```powershell
$Observation=Join-Path $Private 'identity.dpapi'
$HostReport=Join-Path $Private 'host-public.json'
./commissioning/collect-host.ps1 -Output $HostReport -PrivateObservation $Observation
$HostEvidence=Get-Content -LiteralPath $HostReport -Raw | ConvertFrom-Json
if ($HostEvidence.grid_findings -gt 0 -or $HostEvidence.inventory_errors -gt 0 -or -not $HostEvidence.coverage_complete) { throw 'NO-GO: Grid/conflict clearance incomplete; do not proceed' }
if ($HostEvidence.credential_variable_count -gt 0 -or $HostEvidence.production_dsn_variable_count -gt 0) { throw 'NO-GO: review environment privately' }
```

This currently blocks with4 Grid findings and incomplete coverage. Do not delete footprints, stop services/tasks, change settings or invent an all-clear. Operator/independent audit must classify the footprint and complete technical evidence. No-process-found is never absolute absence proof. Do not upload raw host-facts output, SID/GUID/UUID/install identifiers, nonce, DPAPI record, credentials or full private inventory.

## 2. Confirm the specific host, not merely its name

Privately review OS-derived hostname/account matches, Windows11 Pro/build, presence of MachineGuid/install identity/hardware UUID/SID and the salted fingerprint. DPAPI observation is user/installation-bound and must be fresh (one hour for enrollment). Operator explicitly confirms the machine and no-Grid assertion after evidence review. Merely typing hostname or copying a PASS JSON is insufficient. The authorization expires for admission after24h and binds the exact candidate/manifest/software/DB tuple.

## 3. Read-only discovery of existing PostgreSQL

```powershell
./commissioning/postgres-discovery.ps1 -Output (Join-Path $Private 'postgres-existing.json') -CheckReadiness
```

Observed existing service:18.6, data C:/Program Files/PostgreSQL/18/data, port55432, wildcard IPv4/IPv6 listeners. Authentication/grants unknown. Never point setup/app at55432 or change that cluster as a workaround.

## 4. Prepare a NEW isolated cluster — conditional operator procedure only

**Do not execute while step1/2 is NO-GO.** This starts a separate explicitly approved test process, not a service installation. It does not touch existing cluster configuration. Choose a verified-free port; no automatic replacement or existing directory reuse.

```powershell
$PgBin='C:\Program Files\PostgreSQL\18\bin'
$Port=55480
$Db="meta_commission_$Session"; $Role=$Db
$PgData=(Join-Path $Private 'pgdata') -replace '\\','/'
if (Test-Path -LiteralPath $PgData) { throw 'Refuse existing data directory' }
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) { throw 'Port occupied' }
if ((Read-Host 'Only after clearance: type CREATE NEW PRIVATE CLUSTER') -cne 'CREATE NEW PRIVATE CLUSTER') { throw 'Not approved' }
& "$PgBin\initdb.exe" -D $PgData -U meta_commission_bootstrap --auth=scram-sha-256 -W
if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
& "$PgBin\pg_ctl.exe" -D $PgData -l (Join-Path $Private 'private-postgres.log') -o "-h 127.0.0.1 -p $Port" -w start
if ($LASTEXITCODE -ne 0) { throw 'Private cluster start failed' }
& "$PgBin\psql.exe" -h 127.0.0.1 -p $Port -U meta_commission_bootstrap -d postgres -W -v "expected_data_directory=$PgData" -v "expected_port=$Port" -v "test_db=$Db" -v "test_role=$Role" -f commissioning/create-test-db.sql
if ($LASTEXITCODE -ne 0) { throw 'Private DB/role setup refused or failed; no smoke' }
& "$PgBin\psql.exe" -h 127.0.0.1 -p $Port -U meta_commission_bootstrap -d postgres -W -c "\password $Role"
if ($LASTEXITCODE -ne 0) { throw 'Password setup failed' }
```

Passwords are interactive, never command-line values. SQL validates bootstrap/current DB/data directory/port/loopback/initial template databases before writes. PUBLIC CONNECT is revoked only inside this new private cluster. Test role is nonsuperuser, no createdb/createrole/replication/bypassrls/membership and cannot connect elsewhere. Preflight independently verifies these facts. If sharing existing cluster is mandatory, stop and request a separately reviewed isolation design; do not weaken this gate.

## 5. Verify installed MetaScalp and its API

```powershell
$MetaScalpExe=Join-Path $env:LOCALAPPDATA 'MetaScalp\MetaScalp.exe'
if (-not (Test-Path -LiteralPath $MetaScalpExe -PathType Leaf)) { throw 'MetaScalp missing; no automatic install' }
Get-Item -LiteralPath $MetaScalpExe | Select-Object -ExpandProperty VersionInfo | Select-Object FileVersion,ProductVersion
$Signature=Get-AuthenticodeSignature -LiteralPath $MetaScalpExe
if ($Signature.Status -ne 'Valid') { throw 'Unverified MetaScalp signature' }
$MetaScalpHash=(Get-FileHash -LiteralPath $MetaScalpExe -Algorithm SHA256).Hash.ToLowerInvariant()
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -ge 17845 -and $_.LocalPort -le 17855 }
```

Privately verify expected publisher and trusted install provenance before approving the software hash. Current LS5 has two signed0.0.9.0 file candidates but no API listener. Start/configure MetaScalp manually only with operator authorization, or remain NO-GO. No automatic installer/start is included. Enrollment/preflight verify the signed EXE owns the loopback API; preflight uses GET /ping only. Runtime stays pinned to that port/hash and rechecks ownership before requests, without selecting another responder.

## 6. Approve exact host/source/session and prepare pinned environment

Run only after all earlier prerequisites are clear; these commands will currently fail on LS5. No policy file is supplied or preapproved by this package.

```powershell
$Enrollment=Join-Path $Private 'authorization.dpapi'
py -3.12 commissioning/host_identity.py enroll --private-observation $Observation --enrollment $Enrollment --manifest $Manifest --expected-sha $Sha --manifest-sha256 $ManifestHash --database $Db --role $Role --port $Port --data-directory $PgData --metascalp-exe $MetaScalpExe --metascalp-sha256 $MetaScalpHash --operator-approved --confirm-no-grid
if ($LASTEXITCODE -ne 0) { throw 'NO-GO: no specific-host authorization' }
./commissioning/prepare-environment.ps1 -ExpectedComputer LS5 -OperatorApproved -Enrollment $Enrollment -Manifest $Manifest -ExpectedSha $Sha -ManifestSha256 $ManifestHash
```

Prepare script verifies executing root equals trusted source before venv/pip. It installs pinned .[test,archive] only in the packet venv. Never use an unrelated editable checkout or the unrestricted application entrypoint as a commissioning bypass.

## 7. Dedicated-role DSN and mandatory preflight — no smoke launch

Use a clean shell if production/PG/exchange credential variables exist; do not erase persistent settings automatically. Set only this session's dedicated DSN. This example passes the prompted password over stdin, not argv or logs.

```powershell
$Secret=Read-Host 'Dedicated TEST role password' -AsSecureString
$Payload=@{host='127.0.0.1';port="$Port";dbname=$Db;user=$Role;password=([System.Net.NetworkCredential]::new('',$Secret)).Password} | ConvertTo-Json -Compress
$OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$env:META_ANALYSE_COMMISSIONING_DSN=$Payload | & ./.venv/Scripts/python.exe -X utf8 -c "import sys,json;from psycopg.conninfo import make_conninfo;print(make_conninfo(**json.load(sys.stdin)))"
$Payload=$null; $Secret=$null
& ./.venv/Scripts/python.exe commissioning/preflight.py --manifest $Manifest --manifest-sha256 $ManifestHash --expected-sha $Sha --expected-computer LS5 --enrollment $Enrollment --metascalp-exe $MetaScalpExe --output (Join-Path $Private 'preflight.json')
if ($LASTEXITCODE -ne 0) { throw 'NO-GO: preflight failed; do not launch smoke' }
```

Preflight checks source identity/hash coverage, fresh host/Grid/environment, private listener/data directory, PG18 exact role/owner/grants/no-other-DB-CONNECT, signed MetaScalp/API and certificate+hostname verified public REST. TLS is mandatory even without the compatibility flag. No old PASS file authorizes runtime.

**STOP after preflight.** Actual30-minute run requires a separate explicit operator decision and resolved host blockers. Launcher reruns preflight; current package supports smoke30 only, with normal-close request at30min and write draining. This is not a hard exit deadline. Resource observer also accepts30min only. Full scans before MetaScalp requests may add latency; benchmark results without these scans do not certify it.

## Stage decisions, evidence and immediate stop

LS5 30min:NO-GO now. 2h:NO-GO. 24h:NO-GO. All timed tests NOT RUN; queue depth/drop reconciliation remain NULL/UNVERIFIED. No automatic promotion. Later smoke needs host/preflight/session/app/UI/resource/fault/DB-reconciliation logs; observer duration alone is not health PASS.

Stop workload/request safe disconnect on wrong identity/source/DB, Grid conflict/unknown coverage, credentials, TLS failure, wrong MetaScalp owner/API, broad DB privilege, data corruption/stale data marked verified, unrecovered feed, leaked tasks/sockets, early stop acknowledgment, uncontrolled resource growth or missing logs. Never force-kill pending writes to manufacture PASS. Preserve private evidence; do not stop existing services or alter production as rollback. Only explicitly operator-created private resources may later be safely disposed of after separate approval.
