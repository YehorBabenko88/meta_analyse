# Independent lifecycle audit — 2026-10-16

Baseline: PR #4, `codex/windows-order-flow-followup`, fetched head
`729254de3f4614a4717afb0623ffe2ce7c02b670`. Work isolated on
`codex/independent-lifecycle-audit-20261016`; incremental PR targets PR #4 branch.

## Confirmed defects and fixes

- P2: a startup completion callback could restart a session before an awaiting
  stop acquired the lifecycle lock. Stop now claims ownership before yielding,
  shares one cleanup task across callers, and shields it from waiter cancellation.
  Regression reproduces the original timeout and tests cancelled/concurrent stops.
- P2: default Qt editing allowed changing flow identity and cached market values;
  the next incremental update could raise KeyError. Flow and Diagnostics tables
  are read-only, preserving snapshot ownership of displayed data.
- P2: Diagnostics counts and ages sorted lexicographically (`10, 2`). Reuse the
  finite numeric comparator already used by flow cells.

The new regressions failed against the fetched implementation (startup timeout
and editable table). Focused tests pass after the fixes. No microstructure,
MetaScalp levels, feed algorithms, or exchange order paths were changed.

## Validation

Windows 11, Python 3.12.15, PySide6 6.12.0, PostgreSQL 17.6; offscreen Qt,
PYTHONASYNCIODEBUG=1, ResourceWarning and unraisable/thread warnings as errors.
Disposable databases and roles; loopback WebSockets and GET-only mock HTTP.

- Extended integration stress from 20 to 50 sequential connect/disconnect cycles,
  including duplicate clicks, symbol changes, socket/task draining and UNVERIFIED.
- Added window close checks during raw and market collector startup; existing
  coverage closes immediately, during metadata, after initialization errors,
  with 20 active instruments and during blocked database work/disconnection.
- Existing tests cover sorted row identity/add/remove, book/trade gaps, stale and
  restarted data, reconnect health races, OI cadence and Diagnostics resets.
- Focused lifecycle/Qt suite: 23 passed (native exit 0).
- Full Windows suite: 188 passed in 158.43 s, native exit 0. Two warnings
  exposed a test-only global wait_for replacement leaking Event.wait coroutines.
  Replaced it with the collector's real stop event; both OI tests then pass with
  RuntimeWarning promoted to error. No production OI change required.
- GitHub CI for code commit `0d34906`: Windows **188 passed** in 39.63 s;
  Linux **187 passed, 1 skipped** in 16.74 s (Windows-only installer test).
  Both push and PR workflows succeeded; Windows repeated-install checks passed.
  Evidence: https://github.com/YehorBabenko88/meta_analyse/actions/runs/38919355280
  and https://github.com/YehorBabenko88/meta_analyse/actions/runs/38919345539.
  CI artifacts include JUnit, test logs and performance JSON.
- CI synthetic render p95: Windows Server 2025 5.926 ms, Linux 4.242 ms;
  approximately 19,995 callbacks/s, 20 instruments, 10 Hz publication, 3 seconds.
  Worker/loop closure succeeded on both platforms.

Reproduce with an isolated admin DSN:
`python -m pytest -vv --basetemp=../audit-temp --junitxml=../audit.xml`
Run performance: `python scripts/benchmark_flow_ui.py --seconds 10 --output ../performance.json`.

## Performance and limits

20 instruments, 200,000 synthetic callbacks over 10 seconds, publication 10 Hz:
19,971 callbacks/s; render p95 3.118 ms; snapshot-to-render p95 4.014 ms;
Qt heartbeat p95 16.888 ms, max 33.887 ms; close handler 4.202 ms.
Worker and loop closed. Measured concurrently with tests, offscreen.
This isolates callbacks and rendering, not network parsing, SQL or analysis cost.

Freshness is age since local persistence, not exchange completeness: a FRESH
Diagnostics cell does not validate history or negate a reported gap. Flow quality
remains UNVERIFIED after gaps and never asserts VERIFIED market history.
Diagnostics currently exposes book/OI counters, not a complete trade-counter view.
No live exchange/MetaScalp verification or real desktop painting benchmark was
performed. A permanently stuck OS/driver database call cannot be forcibly killed
by asyncio; executor shutdown waits for it. No evidence of such a hang occurred
in the bounded, released database-blocking tests.
