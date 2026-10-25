# ADMINIT G0 — interactive read-only commands when script execution is blocked

Candidate PR36 source: `e2b3469d4949e7346aaa1709620f1a0c419fcbf4`, tree `4f0f4a0c37c00cd5619bae06560e9aaaba95636e`.

The `-File` invocation failed with PowerShell ExecutionPolicy UnauthorizedAccess **before** running any G0 script body. Do not use `-ExecutionPolicy Bypass`, `Set-ExecutionPolicy`, `Unblock-File`, execution through encoded command, copied script text, or a different host to evade organization policy.

The following commands are **individual read-only diagnostic commands**, to be typed by the ADMINIT operator in an already permitted interactive PowerShell session. First confirm these interactive commands are permitted by the administrator/organizational policy. If they are prohibited or constrained by language mode, stop and request an approved signed-script path. They do **not** run the blocked G0 script and do not themselves imply an authorization to execute other programs.

## Restricted initial diagnostics (no elevation)

Open PowerShell normally (do not use Run as Administrator):

```powershell
Get-ExecutionPolicy -List
$ExecutionContext.SessionState.LanguageMode
$PSVersionTable.PSVersion
[Environment]::Is64BitOperatingSystem
```

Do not publish full command outputs if they expose paths or identities. In a private ADMINIT session, set the repository path to **your actual existing isolated checkout**, not a default or guessed path:

```powershell
$repo = 'C:\MetaAnalyse-Test\adminit-checkout'  # replace with confirmed existing checkout
git -C $repo rev-parse HEAD
git -C $repo rev-parse 'HEAD^{tree}'
git -C $repo status --porcelain
```

These must match PR36 `e2b3469d4949e7346aaa1709620f1a0c419fcbf4`, tree `4f0f4a0c37c00cd5619bae06560e9aaaba95636e`, and empty git status. If not: BLOCKED.

After confirming interactive diagnostics are permitted, use the following as **separate commands**, not pasted or invoked as a script:

```powershell
Get-CimInstance Win32_Service | Where-Object { $_.Name -like 'postgresql*' } | Select-Object Name,State
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in @(5432,55432,55480) } | Select-Object LocalAddress,LocalPort
Get-Process -Name MetaScalp -ErrorAction SilentlyContinue | Measure-Object
Get-Command py,python,git -ErrorAction SilentlyContinue | Select-Object Name,CommandType
```

Do not connect to PostgreSQL, stop services, change listening ports, initialize directories, install software, modify execution policy, or use trading credentials.

## What this proves — and what it does not

It proves only that selected read-only commands were manually observed, subject to operator control and output review. This is a **partial G0 observation**, not G0 PASS. It does not attest physical machine identity, protected-process inventory, Windows trust, complete Grid coverage, PostgreSQL system_identifier/role, backup ownership, UI readiness or isolation.

Record only sanitized verdicts: source SHA/tree match (yes/no), clean worktree (yes/no), PowerShell policy permits a signed G0 path (yes/no), PostgreSQL service count, whether candidate port is occupied, MetaScalp process count, and whether any diagnostic command failed. Preserve detailed output privately on ADMINIT. Do not upload machine identifiers, username, SID, credentials, database connection strings, paths or raw process lists.

If G0 script execution is required for formal admission, request an authorized code-signed execution path from the ADMINIT security administrator. An interactive observation cannot silently replace mandatory signed script evidence. **G1/G2/30m/2h/24h remain blocked.**
