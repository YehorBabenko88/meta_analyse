# Order Flow incremental Qt audit — 2026-10-15

Requested starting point: PR #3, branch `codex/windows-lifecycle-audit-v2`, commit `897d306213b94cb7fa2cb51b100110c0c1796f82`. During work, preserve the author's concurrent indentation fix `f92f1ec`. Base then advanced to `6530b7e53e90495c43d7ada3324abb442b9f086d`; user explicitly chose a new branch/PR preserving PR #3 history rather than force push. Reconciled branch: `codex/windows-order-flow-followup`. No merge, force push, real orders or MetaScalp level writes.

## Findings and fixes

| Finding | Evidence / correction |
| --- | --- |
| Both Actions jobs fail before running tests. | Original run [38767847052](https://github.com/YehorBabenko88/meta_analyse/actions/runs/38767847052) reports `IndentationError` in desktop.py. After indentation correction, missing `flow_diff` prevents import. Preserve f92f1ec and reconcile the now-existing base helper; compilation/import and Qt regressions pass. |
| Partial update uses snapshot positions as visual Qt positions. | Descending symbol sort and ascending delta sort reproduce overwriting another instrument. Map symbol to current visual position before updating, with sorting temporarily disabled. Rebuild all rows on membership/order changes. |
| Numeric columns sort lexically; mixed numeric/text comparison is nontransitive. | Values 9/20/100 sort incorrectly. Regression with malformed `1a` also fails. Use finite-number/text categories and numeric comparison within the numeric category. |
| Incremental repaint forces sorting on and replaces unchanged cells. | Preserve sorting/update state in finally; update existing cell text/brush only when needed. Unchanged snapshots retain item identity and current selection; quality transitions update colors. |
| Disconnect under buffered feed traffic can wait the default 10-second WebSocket close timeout. | Debug-mode real loopback stress reproduces a task stuck in context exit. Set close_timeout=2 for raw trade, orderbook and terminal transports, without modifying analytics algorithms. |
| Closing immediately after disconnect can cancel the same cleanup twice and abandon socket transports. | Windows debug stress and ResourceWarning expose leaked sockets. Await owner-driven session/monitor shutdown before cancelling remaining asyncio tasks. Both close variants now pass with resource/thread/unraisable warnings treated as errors. |
| Linux regression output is piped through tee without an explicit pipefail shell. | Use explicit `shell: bash`, which runs with -e -o pipefail, preserving pytest failure status. The subsequent Linux fixture failure correctly fails Actions. |
| A close-test gate can miss Linux's short stopping transition. | Initial follow-up run [38770192828](https://github.com/YehorBabenko88/meta_analyse/actions/runs/38770192828): Windows passed; Linux failed waiting for a transient GUI status. Use a worker-side cleanup barrier instead of polling a transient 100ms snapshot. The test still requires connected state, four sockets and all forty trade/book topics. |

The original audit remains in `docs/CODEX_WINDOWS_AUDIT.md`. This follow-up does not edit feed_watchdog.py, flow_bridge.py, orderbook.py, footprint.py or microstructure algorithms. Transport-only raw_trades.py/orderbook_stream.py changes bound close handshakes.

## Regression and lifecycle coverage

- Table: changed data under ascending/descending symbol and delta sorting; insertion, deletion, same-length reorder and empty snapshot; numeric and malformed values; unchanged item/selection identity; changed quality colors; sorting disabled by the user.
- Twenty connect/disconnect cycles, repeated clicks, changing selected symbols, real loopback WebSockets and isolated PostgreSQL. Assert collector tasks gone, socket handlers closed, no session/startup references, all historical rows UNVERIFIED.
- Close with twenty instruments, two trade plus two book sockets and all forty subscribed topics. Block real DB persistence at its boundary, verify Qt timer dispatch while cleanup waits, release DB operation, verify worker/loop/clients close. Repeat with disconnect already in progress.
- Local actual Windows 11/Python 3.12.15/PySide6 6.12.0/PostgreSQL 17.6: full reconciled suite **114 passed in 76.11s, native exit 0**. Corrected Linux cleanup-barrier test subsequently passed both variants locally. CI supplies authoritative exact-head cross-platform results and artifacts.

## Native Windows performance

Ten-second runs, twenty symbols, target 20,000 synthetic execution callbacks/s, normal 10Hz immutable publication, actual native Qt `windows` plugin. The worker invokes the real bridge callback; the Qt loop handles queued snapshots, a 10ms heartbeat and actual table updates. Runs are sequential, not competing benchmark processes. Each run also performs 300 iterations per microbenchmark case. Full reference replaces every cell, matching the previous full-repaint strategy; it is a controlled reference, not execution of broken commit897d3062.

| Metric | Partial updates | Full replacement reference |
| --- | ---: | ---: |
| Processed callbacks | 200,000 | 200,000 |
| Actual callbacks/s | 19,977 | 19,987 |
| Render median | 1.681 ms | 3.165 ms |
| Render p95 | 2.794 ms | 4.152 ms |
| Render maximum | 3.164 ms | 5.878 ms |
| Queued snapshot-to-render p95 | 3.216 ms | 5.040 ms |
| Qt heartbeat p95, target10ms | 16.818 ms | 20.257 ms |
| Qt heartbeat maximum | 26.475 ms | 25.510 ms |
| Close-event handler duration | 4.206 ms | 4.110 ms |
| Process CPU, one-core equivalent | 33.4% | 36.3% |
| Unchanged snapshot median | 0.062 ms | 1.385 ms |
| One changed symbol median | 0.231 ms | 1.418 ms |
| All twenty changed median | 0.906 ms | 1.350 ms |

Render p95 was about 33% lower in this pair of runs. The worst heartbeat was slightly higher for partial updates; do not generalize every latency statistic as improved. Both processes drained workers and closed loops. Close-event duration measures Qt handler responsiveness, not total network/DB shutdown time.

These are callback/Qt measurements with UNVERIFIED synthetic rows, **not exchange-to-database throughput**. They exclude network parsing, SQL persistence and microstructure computation. Python process CPU includes worker and GUI; it is not machine-wide utilization. Hardware/OS timer scheduling and repaint visibility affect results. CI records three-second offscreen diagnostics on both platforms without brittle machine-specific timing gates.

## Reproduce

Install Python3.12 dependencies with `python -m pip install -c requirements.lock -e ".[test]"`. For the regression suite, use the disposable-PostgreSQL procedure in the original audit and a fresh scratch directory:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONASYNCIODEBUG = '1'
$env:META_ANALYSE_TEST_ADMIN_DSN = 'host=127.0.0.1 port=55439 user=audit dbname=postgres'
.venv\Scripts\python -m compileall -q src scripts
.venv\Scripts\python -m pytest -q --basetemp=..\work\pytest-flow --junitxml=..\work\flow.xml
.venv\Scripts\python scripts/benchmark_flow_ui.py --platform windows --seconds 10 --renderer partial --output ..\work\partial.json
.venv\Scripts\python scripts/benchmark_flow_ui.py --platform windows --seconds 10 --renderer full --output ..\work\full.json
```

On Linux use `--platform offscreen`. GitHub Actions artifacts `windows-test-evidence` and `linux-test-evidence` now include `ui-performance.json` alongside JUnit/test output; Windows also retains the temporary PostgreSQL log.

## Remaining risks

- Ten seconds and twenty instruments provide a focused regression measurement, not a long-duration/memory-growth or production load guarantee. No actual exchange or MetaScalp-account integration was exercised.
- A two-second graceful close can abort a slow peer rather than complete its handshake; restarting remains unverified. Raw publicTrade WebSocket history is not guaranteed complete.
- Cancelling to_thread cannot interrupt an executing native SQL call. Final shutdown still waits for the bounded DB operation/executor; the Qt handler remains responsive. Synchronous legacy profile/fill persistence can delay the worker.
- Publication stays10Hz. Higher-rate input is coalesced into snapshots; per-event rendering is neither attempted nor measured. No throughput claim is made for PostgreSQL ingestion.
- Current market-quality and analytics decisions are preserved. The benchmark uses synthetic data and does not certify live trading readiness.
