# Review coverage PR47: 36 changed paths

Exact reviewed HEAD59626930a911c0dde330f7760c78ccd99468a1f4. This is file-level source-review accounting, not measured branch/line coverage. Windows Native/SCM unchanged dependencies additionally reviewed; C# ABI/PPL runtime remains BLOCKED. No production readiness is inferred.

| File | Area | Evidence and limit |
|---|---|---|
| `.github/workflows/adminit-final-synthetic.yml` | CI/privacy | source/lint/synthetic; hosted BLOCKED |
| `.github/workflows/ci.yml` | CI/privacy | source/lint/synthetic; hosted BLOCKED |
| `.github/workflows/storage-ingestion.yml` | CI/privacy | source/lint/synthetic; hosted BLOCKED |
| `ADMINIT_DEPLOYMENT_AND_ACCEPTANCE_RU.md` | Documentation | reviewed provenance/limits/authorization wording; no runtime claim |
| `POSTGRES_ADMINIT_DEPLOYMENT_RU.md` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `commissioning/initialize-private-schema.py` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `commissioning/preflight.py` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `commissioning/run_readonly.py` | Desktop/commissioning | caller source + fake/offscreen checks; physical BLOCKED |
| `commissioning/stage_acceptance.py` | G0-G5 | pure negative/source checks; no execution authority |
| `docs/superpowers/plans/2026-10-25-adminit-final-integration.md` | Documentation | reviewed provenance/limits/authorization wording; no runtime claim |
| `scripts/check_final_integration_junit.py` | CI/privacy | source/lint/synthetic; hosted BLOCKED |
| `scripts/integration_synthetic_boundary.py` | CI/privacy | source/lint/synthetic; hosted BLOCKED |
| `scripts/public_bybit_e2e_probe.py` | Bybit/E2E | independent source + fake transport/persistence; public network BLOCKED |
| `src/meta_analyse/desktop.py` | Desktop/commissioning | caller source + fake/offscreen checks; physical BLOCKED |
| `src/meta_analyse/orderbook_stream.py` | Bybit/E2E | independent source + fake transport/persistence; public network BLOCKED |
| `src/meta_analyse/pg_authorized_connection.py` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `src/meta_analyse/pg_checkpoint_witness.py` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `src/meta_analyse/pg_cluster_attestation.py` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `src/meta_analyse/pg_cluster_plan.py` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `src/meta_analyse/storage.py` | Desktop/commissioning | caller source + fake/offscreen checks; physical BLOCKED |
| `tests/test_adminit_commissioning.py` | Regression tests | selected source suites executed, except explicitly deselected live DPAPI |
| `tests/test_bybit_collector_witness.py` | Regression tests | selected source suites executed, except explicitly deselected live DPAPI |
| `tests/test_bybit_stream_witness.py` | Regression tests | selected source suites executed, except explicitly deselected live DPAPI |
| `tests/test_final_integration_junit.py` | Regression tests | selected source suites executed, except explicitly deselected live DPAPI |
| `tests/test_final_integration_workflow.py` | Regression tests | selected source suites executed, except explicitly deselected live DPAPI |
| `tests/test_host_identity_authorization.py` | Regression tests | selected source suites executed, except explicitly deselected live DPAPI |
| `tests/test_pg_catalog_binding.py` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `tests/test_pg_checkpoint_witness.py` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `tests/test_pg_cluster_attestation.py` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `tests/test_pg_cluster_connection.py` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `tests/test_pg_cluster_plan.py` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `tests/test_pg_commissioning_binding.py` | PostgreSQL | independent source + fake regressions; realSQL BLOCKED |
| `tests/test_public_bybit_e2e_probe.py` | Regression tests | selected source suites executed, except explicitly deselected live DPAPI |
| `tests/test_public_evidence_workflows.py` | Regression tests | selected source suites executed, except explicitly deselected live DPAPI |
| `tests/test_scm_cooccurrence_independent.py` | Regression tests | selected source suites executed, except explicitly deselected live DPAPI |
| `tests/test_stage_acceptance.py` | G0-G5 | pure negative/source checks; no execution authority |
