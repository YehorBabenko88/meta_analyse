# Codex parallel work assignment — Meta Analyse

## Repository access
- GitHub: https://github.com/YehorBabenko88/meta_analyse
- Base branch: feat/metascalp-companion-v01
- Existing PR: https://github.com/YehorBabenko88/meta_analyse/pull/1
- Create **your own branch** named codex/windows-lifecycle-audit from the current base branch.
- Open a PR targeting feat/metascalp-companion-v01. Do not merge, force-push, or modify production infrastructure.
- Authentication: use existing GitHub authorization in Codex or `gh auth login` on the user's own computer. Never paste tokens or secrets into chat, commits, or logs.

## Scope — Codex owns Windows and lifecycle audit
1. Reproduce install and launch on Windows 11 with Python 3.12, PySide6 and a disposable isolated PostgreSQL database. Document exact commands and any missing dependencies.
2. Audit `src/meta_analyse/desktop.py` and `analysis_session.py` for Qt cross-thread access, start/stop races, blocking shutdown, partial initialization, task leaks, reconnection after failure and repeated clicking.
3. Replace shared mutable GUI flags with thread-safe signals or immutable snapshots. Ensure widgets are changed **only on Qt main thread**.
4. Add an end-to-end smoke test with mock exchange, mock MetaScalp and temporary DB or isolated test fixture; no real exchange orders, no writes to MetaScalp.
5. Add tests for offline startup, invalid DSN, invalid tick size, disconnected WebSocket, UI closure during startup, shutdown and restart.
6. Review `install.ps1` and `pyproject.toml` for idempotent setup, dependency pinning and secure handling of credentials.
7. Review CI coverage, including Windows, Qt offscreen mode and database integration. Fix confirmed failures and attach logs.
8. Produce `docs/CODEX_WINDOWS_AUDIT.md` with reproducible steps, findings, severity, fixes and remaining risks.

## Critical safety invariants
- Read-only exchange API and paper-only execution. Never place live orders.
- Keep PostgreSQL writes inside `meta_analyse` schema.
- Preserve manually created MetaScalp levels; never bulk-delete chart levels.
- Unknown, stale, gapped or restarted feeds MUST NOT be marked verified.
- Raw publicTrade data cannot guarantee complete history by WebSocket alone.
- Do not claim live-ready without actual Windows and PostgreSQL integration evidence.

## Coordination
- Avoid editing `feed_watchdog.py`, `flow_bridge.py`, `orderbook.py`, `footprint.py`, and microstructure algorithms; these are being developed separately.
- You may edit `desktop.py`, `analysis_session.py`, installer and test infrastructure in your own branch.
- Commit small focused changes; run tests and GitHub Actions; report SHA, CI links, exact failures and reproducibility.
- If work conflicts with the base branch, rebase your branch and resolve explicitly; never overwrite others' commits.
