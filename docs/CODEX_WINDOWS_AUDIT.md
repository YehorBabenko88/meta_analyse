# Windows lifecycle audit — 2026-10-15

Scope: `docs/CODEX_HANDOFF.md`. Initial base `528467d32dba06b350819c6fed5de8af926adb70`; reconciled with `feat/metascalp-companion-v01` at `69b45d047a5f14fbaa497575b4e55e14ab7c25f7`. With explicit user authorization, publish rebased work as `codex/windows-lifecycle-audit-v2`; original branch/PR #2 history remains intact. No merge, force push, production changes, real orders or MetaScalp level writes.

## Environment and evidence

- Actual workstation: Windows 11 Pro 10.0.26300, isolated Python 3.12.15, PySide6 6.12.0, psycopg 3.3.6, websockets 15.0.1.
- Machine initially had Python 3.14 only and no PostgreSQL. Python 3.12 was provisioned with uv; PostgreSQL 17.6 portable binaries and temporary cluster live under scratch `work/`. No system PostgreSQL service installed.
- PostgreSQL binds loopback only. Tests create random databases and owner roles and drop only those test resources. Application DDL/DML stays in `meta_analyse`; a `public.audit_sentinel` row is verified unchanged.
- Baseline: **63 passed**. Expanded suite after incorporating upstream tests: **96 tests**, including actual Windows Qt and PostgreSQL integration. Final native exit and CI evidence appear below.
- Native Qt `windows` plugin: actual window displayed with stylesheet, deterministic offline message rendered, screenshot captured, asynchronous close completed, worker stopped and loop closed. Automated GUI tests also run offscreen on Windows.
- Installer executed twice against the same isolated path containing a space; final imports and `pip check` succeeded. Failure regression invokes real PowerShell and pip on an invalid source checkout.

## Findings and fixes

| Severity | Confirmed finding | Fix / regression evidence |
| --- | --- | --- |
| High | GUI reads worker-owned symbols/fills/positions and writes paper fields concurrently. | Worker-owned `DesktopService`; frozen tuple/dataclass snapshots via queued Qt signals. GUI sends captured configuration values to worker. |
| High | Close blocks Qt up to five seconds and stops loop with pending tasks and open HTTP clients. | Async cancellation/drain; Qt timer closes window after worker exits. HTTP clients, executor, async generators and loop are closed. |
| High | Disconnect during metadata/startup fails to cancel connection; duplicate/queued starts can overtake stop. | Track/cancel startup, reject starts during lifecycle transitions, serialize cleanup. Tests gate each transition. |
| High | Partial startup leaks tasks; market stop failure skips raw cleanup. | Always clean both collectors and invalidate analysis state; test both initialization failures, cleanup failure, cancellation and restart. |
| High | Real PostgreSQL concurrent monitor/raw schema creation raises `UniqueViolation` despite `IF NOT EXISTS`. | Shared transaction advisory lock in all three schema initializers. End-to-end test starts monitoring and raw feeds concurrently. |
| Medium | Repeated disconnect publishes disconnected before prior cleanup ends, allowing a conflicting restart. | Repeated requests join one disconnect task; session retained until cleanup finishes. Gated regression test. |
| Medium | Invalid `SSL_CERT_FILE` kills worker during second client construction, losing first client and leaving loop open. | Sequential assignments retain partial resources; guarded initialization reports sanitized error and drains/closes everything. Requests after worker failure rejected. |
| Medium | Dead collector task is silent while GUI implies a running connection. | Health supervision detects completed/failed tasks, drains siblings, reports failure and unverified data. |
| Medium | Offline failures appear only in console, with raw exception text. | Visible operation/exception-type messages exclude DSNs, passwords and payloads. Monitor disconnect/retry status reaches GUI. |
| Medium | Invalid ticks inconsistently rejected; infinity accepted. | Require finite positive tick sizes before allocating collectors. Test zero, negative, NaN and infinity. |
| Medium | Unbounded DB connection/query/lock waits. | Five-second connection, statement and lock timeouts; actual PostgreSQL settings asserted. |
| High | Installer reports success and creates launcher after native pip failure. | Check every native exit, verify Python 3.12/import, reuse venv, create launcher only after success. Real failure regression. |
| Medium | Deployment dependency ranges drift; CI lacks DB and actual Qt lifecycle tests. | Tested transitive versions in `requirements.lock`; installer/CI use constraints. Windows/Linux offscreen+PostgreSQL jobs upload logs/JUnit. |
| High | Windows CI prints passing assertions but Python aborts during native Qt finalization. | One session QApplication; explicitly dispose widgets and native application and explicitly dispose the native QApplication before interpreter finalization. Native exit remains mandatory. |

Support edits to `storage.py`, `raw_store.py` and `market_store.py` fix the reproduced schema race. `runtime.py` reports connectivity and clears running state on cancellation. Excluded files `feed_watchdog.py`, `flow_bridge.py`, `orderbook.py`, `footprint.py` and microstructure algorithms were not edited.

## Reproduction

From the repository root on Windows 11 with Python 3.12:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -c requirements.lock -e ".[test]"
.venv\Scripts\python -m pip check
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONASYNCIODEBUG = '1'
.venv\Scripts\python -m compileall -q src
# Use a fresh WorkRoot. The script creates/stops its own loopback cluster.
.\scripts\test-windows.ps1 -Python (Resolve-Path .venv\Scripts\python.exe).Path `
  -PgBin 'C:\path\to\pgsql\bin' -WorkRoot '..\work\audit-ci'
```

Without `-PgBin`, the script discovers installed binaries or downloads the tested portable 17.6 archive and checks pinned SHA256. It does not connect to an existing production DB. Trust authentication is restricted to this disposable loopback test cluster.

For an already provisioned **disposable** admin DB:

```powershell
$env:META_ANALYSE_TEST_ADMIN_DSN = 'host=127.0.0.1 port=55439 user=audit dbname=postgres'
.venv\Scripts\python -m pytest -q --basetemp=..\work\pytest-audit --junitxml=..\work\tests.xml
```

Without this test DSN, the two PostgreSQL-backed tests skip explicitly. CI always provides it. This workstation needed workspace-local `--basetemp` because an existing system-temp pytest directory denied access; no system ACL was changed.

Installer idempotency:

```powershell
.\install.ps1 -Python (Resolve-Path .venv\Scripts\python.exe).Path -InstallRoot '..\work\installer target'
.\install.ps1 -Python (Resolve-Path .venv\Scripts\python.exe).Path -InstallRoot '..\work\installer target'
& '..\work\installer target\venv\Scripts\python.exe' -m pip check
```

Installer writes no credentials/DSN to launcher or configuration. Keep the source checkout available (editable install). An incompatible existing venv is rejected rather than silently replaced. Refresh constraints deliberately with `uv pip compile pyproject.toml --extra test --universal --output-file requirements.lock` and retest both platforms.

## Coverage

- Qt widgets: offline rendering, closure during watchlist/metadata startup, partial client construction failure, loop/thread/client cleanup.
- Session: invalid ticks, concurrent/delayed start-stop, partial initialization, cleanup failure and restart.
- Worker: sanitized errors, duplicate monitor start, metadata cancellation, overlapping disconnects, collector death/sibling drainage.
- Full smoke: actual Qt window/async worker; mock HTTP exchange+MetaScalp transports; real loopback WebSockets; durable executions/books/open-interest/gaps; forced WS disconnect/reconnect; disconnect/restart; repeated starts and shutdown. HTTP mock rejects all write methods; no level endpoint accessed. Quality remains UNVERIFIED after reconnect/restart.
- Installer: real PowerShell/pip failure, repeat success and dependency consistency.

## CI and final results

Initial run: https://github.com/YehorBabenko88/meta_analyse/actions/runs/38763408831 . Linux passed; Windows assertions passed (85) but process failed during Qt finalization. This was investigated as a real failure, not bypassed. Explicit native QApplication disposal gave four consecutive clean exits in independent reproduction; full corrected verification is recorded here after CI completes.

A subsequent Windows run (38764445003) exposed a smoke-fixture race: it disconnected after the peer sent its second frame but before the worker committed it, then expected three durable rows. The test now waits on durable DB counts before intentional cancellation, preserving its assertions without arbitrary sleeps.

Workflow artifacts contain test output, JUnit and the Windows isolated PostgreSQL log. PR and final run links will be added after corrected runs finish.

## Remaining risks / limits

- Evidence covers Windows lifecycle, simulated network peers and real isolated PostgreSQL; **not live-ready certification**. Real MetaScalp/exchange-account integration was not exercised.
- WebSocket publicTrade cannot guarantee complete history. Gapped/restarted feeds remain unverified; no promotion to VERIFIED added.
- Legacy synchronous profile/fill DB operations in `Runtime.receive` can delay the worker until the new timeout. Qt remains independent. An async persistence queue needs a separate ordering/backpressure design.
- Cancelling `asyncio.to_thread` does not interrupt an active native DB call. Shutdown drains the executor and can wait for bounded DB operations while Qt stays responsive. No unsafe native thread termination introduced.
- Lock pins runtime/test resolution but does not hash every package or fully pin isolated setuptools build tooling. Source-checkout installation is not a signed standalone executable.
- Metadata allows Python 3.11; this audit and CI target Python 3.12. Winget bootstrap was reviewed; explicit-interpreter installation was exercised.
- Long-duration/high-rate load and excluded microstructure algorithms require separate evidence. Test PostgreSQL binaries are never deployed to production.
