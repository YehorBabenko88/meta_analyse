# Windows lifecycle audit implementation plan

> Execute inline using superpowers:executing-plans; regression tests precede fixes.

Goal: fulfill docs/CODEX_HANDOFF.md with Windows evidence and a PR.
Architecture: asyncio owns services; Qt receives immutable queued snapshots. Startup, cancellation and cleanup are serialized. External services are replaced at transport boundaries in tests.
Tech stack: Python 3.12, PySide6, pytest, psycopg, PostgreSQL, GitHub Actions.
Spec: docs/CODEX_HANDOFF.md.

## Constraints
Own branch only; no merge or force push. No exchange orders, MetaScalp level writes or production DB. Leave microstructure and flow_bridge.py untouched.

## Review focus
Close while metadata/DB starts; double start/stop; cleanup after partial failure; credentials in errors; reconnect cannot imply verified history.

## Tasks
- [x] 1. Reproduce Windows installation and baseline suite. Record missing Python 3.12 and PostgreSQL; provision isolated runtimes.
- [x] 2. Session lifecycle: tests in tests/test_session_lifecycle.py for invalid ticks, concurrent start/stop, failed/cancelled initialization, cleanup failure and restart. Fix analysis_session.py, run targeted tests and commit.
- [x] 3. Desktop lifecycle: tests in tests/test_desktop_lifecycle.py for offline startup, duplicate clicks, disconnect/close during startup, visible errors, main-thread rendering, client/task cleanup and restart. Fix desktop.py with worker-owned services, immutable snapshots and queued Qt signals; run tests and commit.
- [x] 4. Add local mock HTTP/WebSocket and isolated PostgreSQL end-to-end tests, invalid DSN test, secure bounded DB connects; run and commit.
- [x] 5. Exercise installer twice with isolated target. Fix native command failure handling and Python detection, lock tested dependencies; add Windows/offscreen and PostgreSQL CI with logs. Run suite, commit.
- [ ] 6. Review diff, run final verification, write docs/CODEX_WINDOWS_AUDIT.md with exact evidence and risks. Push own branch, create PR into feat/metascalp-companion-v01, inspect Actions and report.

Ruling: user explicitly requested autonomous execution; proceed without plan approval. Fresh clone provides isolation without a second checkout.

Review ledger: independent review found overlapping disconnect and client-construction failures; both reproduced and fixed. Windows CI exposed native QApplication finalization crash despite passing assertions; explicit fixture teardown fixed it, with clean native exit verified. Final CI and PR evidence pending.
