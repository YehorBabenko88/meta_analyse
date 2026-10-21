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
    "test_contended_advisory_lock_fails_without_partial_import",
    "test_contended_import_waits_on_server_and_resumes",
)

def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: check_integration_postgres.py FULL_JUNIT_XML [--allow-skip TEST_NAME ...]")
    checker = Path(__file__).with_name("check_integration_junit.py")
    command = [sys.executable, str(checker), sys.argv[1], "--minimum", str(len(REQUIRED)), *sys.argv[2:]]
    for name in REQUIRED:
        command.extend(["--require-identity", "tests.test_storage_ingestion_postgres." + name])
    for name in ("test_shutdown_waits_for_thread_write_before_cancelled_task_finishes",
                 "test_repeated_cancellation_does_not_abandon_write",
                 "test_failed_write_after_cancellation_waits_for_rollback",
                 "test_write_failure_without_cancellation_is_propagated",
                 "test_successful_write_returns_result"):
        command.extend(["--require-identity", "tests.test_integration_contract_shutdown." + name])
    raise SystemExit(subprocess.call(command))

if __name__ == "__main__":
    main()
