# UI benchmark: source acceptance and CI remediation

Base: exact Draft PR #59 `b6aeaf99ea00c3550a87f9ecde74a4e73bd248fe`.
The original PR and its branch are unchanged. This branch is synthetic CI work;
physical ADMINIT G0/G1, deployment and merge are not performed or authorized.

## Root cause and RED

On the exact base source, the three-second offscreen benchmark exits 1 with
`statistics.StatisticsError: no median for empty data`. The benchmark initializes
`Runtime(None, None)` but leaves `DesktopService.flow_state='disconnected'`.
The real `_flow_execution` guard therefore rejects every synthetic callback.
The producer's event counter counts attempts, not accepted bridge updates.
`publish_loop` replaces the manually seeded microbenchmark rows with empty bridge
snapshots; clearing `frames` correctly exposes the missing workload samples.
Neither bypassing this production guard nor retaining microbenchmark frames is a fix.

The local Python environment has an older editable install. Exact reproduction
requires `PYTHONPATH=<this checkout>/src`; pytest already declares `pythonpath=src`.
The first unbound control was not accepted as exact-source evidence.

## Changes and regression witnesses

- Synthetic initialization selects the existing admitted `connecting` state;
  no clients/session are created. Every row remains UNVERIFIED. No production
  `src/` or `commissioning/` predicate changes.
- Independent stages count publications, twenty-row snapshots, Qt receipt,
  repaint, actual table rows, bridge rows, asynchronous/UI/thread errors and
  bounded timestamp-map overflow. Counts saturate; no identities, symbols,
  paths, DSNs, exception messages or hostnames are published.
- Empty render samples cause `FAIL_CLOSED / NO_RENDER_SAMPLES`, exit 1, null
  render metrics. Missing latency/heartbeat or invalid measurements also refuse.
- Producer futures are inspected with `result()` on completion and after Qt
  exits. Producer failure, unhandled async task failure, late repaint failure
  and shutdown failure have deterministic negative tests. Exceptions do not
  become Qt raw stderr evidence or successful shutdown merely because a worker
  stopped and an event loop closed.
- A parent process supervises the CLI benchmark child with duration + 15 seconds.
  A deadlocked Qt loop or stalled shutdown cannot block that parent indefinitely.
  `subprocess.run` kills/waits its child on timeout; the child owns its worker
  thread, and creates no subprocesses. No Qt objects are destroyed by the parent.
  Timeout publishes unavailable metrics/counters, never invented zero samples.
  OS process creation and filesystem operations remain subject to workflow timeout.
- Structured benchmark publication has a separate strict three-file inventory,
  canonical JSON, SHA256, exact source/tree/run/attempt/job provenance, and
  success/failure outcome binding. A failed step cannot publish stale public PASS.
  Malformed/private values, unexpected keys, non-finite numbers, tampering and
  attempt replay are rejected. Existing JUnit privacy publication is retained.

## Metrics and thresholds

Render median/p95/max, queued snapshot latency, heartbeat, callback event rate,
one-core-equivalent CPU and shutdown duration remain real measured quantities.
`render_fps` counts completed twenty-row table-update callbacks per measured
second, including periodic refreshes; it is not physical display/GPU frame rate.
`python_heap_peak_bytes` is tracemalloc's Python allocation peak, **not RSS or Qt
native memory**. Instrumentation overhead is included in timing/CPU; old timings
without tracemalloc are not directly comparable.

The base benchmark and existing follow-up documentation explicitly have no
hardware-specific timing pass thresholds. None have been disabled or relaxed.
Admission thresholds are positive finite workload/duration, twenty bridge/table
rows, nonempty render/latency/heartbeat samples, no observed async/UI/thread
errors, and completed worker/loop shutdown. Synthetic workload is bounded to
60 seconds and 100,000 callbacks/second. This is not an exchange/SQL throughput
or physical ADMINIT readiness measurement.

## Reproduction

Use a pinned Python 3.12 environment installed from this checkout with
`python -m pip install -c requirements.lock -e ".[test,archive]"`.
Linux also needs the existing `libegl1 libopengl0 libxkbcommon0` packages.

```text
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_ui_benchmark.py
python scripts/benchmark_flow_ui.py --seconds 3 --output <owned-external-output>/ui.json
```

On Windows use PowerShell `$env:QT_QPA_PLATFORM='offscreen'`. For a shared editable
environment explicitly bind `PYTHONPATH` to this checkout's `src` first.
The `--_worker` switch is internal; CI invokes the supervising default entrypoint.
Tests use in-process Qt to exercise actual signals and callbacks; timeout unit
testing substitutes the standard-library TimeoutExpired boundary. The CLI run
and hosted Windows/Linux jobs exercise the real supervising subprocess.

All existing synthetic, full CI, PostgreSQL18, privacy and native/kernel offline
gates remain enabled for the new branch. Hosted success and artifacts are separate
acceptance requirements; pending/skipped/queued jobs do not establish PASS.
Exact final HEAD/tree, hosted URLs, JUnit/ZIP verification and final verdict are
recorded in the accompanying external evidence report after execution.
