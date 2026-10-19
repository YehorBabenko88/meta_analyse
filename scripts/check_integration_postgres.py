"""Fail-closed required PostgreSQL integration test manifest.

Run against the full JUnit report of the combined PR #10 checkout, not the
isolated PR #9 baseline. No optional/skipped database tests are accepted.
"""
from pathlib import Path
import subprocess
import sys

REQUIRED = (
    "test_resume_and_deduplication",
    "test_concurrent_sources_same_symbol",
    "test_conflicting_archive_rolls_back_batch_and_checkpoint",
    "test_partial_batch_failure_keeps_previous_committed_checkpoint",
    "test_resume_after_failed_batch_and_repaired_archive_conflict",
    "test_concurrent_identical_archive_is_idempotent",
    "test_failed_import_status_preserves_committed_checkpoint",
    "test_orderflow_reader_returns_exact_aliases",
    "test_unlock_failure_does_not_mask_original_import_error",
)

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check_integration_postgres.py FULL_JUNIT_XML")
    checker = Path(__file__).with_name("check_integration_junit.py")
    command = [sys.executable, str(checker), sys.argv[1], "--minimum", "9"]
    # Only the Linux-inapplicable Windows installer test may be skipped.\n    # Required PostgreSQL cases remain non-skippable.\n    command.extend(["--allow-skip", "test_failed_pip_install_never_reports_success_or_creates_launcher"])\n    for name in REQUIRED:\n        command.extend(["--require-exact", name])
    raise SystemExit(subprocess.call(command))

if __name__ == "__main__":
    main()
