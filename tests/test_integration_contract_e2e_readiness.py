"""Offline negative acceptance cases for G0 and full E2E evidence."""
from scripts.check_e2e_readiness_contract import classify


def test_all_verified_sources_can_pass():
    assert classify(general_ci="success", synthetic_ci="success",
        frozen_object_present=True, postgres_attested=True,
        full_e2e_witness=True, exact_source_bound=True,
        unexpected_skips=0, artifact_inventory_verified=True) == "PASS"


def test_queued_ci_is_blocked():
    assert classify(general_ci="queued", synthetic_ci="success",
        frozen_object_present=True, postgres_attested=True,
        full_e2e_witness=True) == "BLOCKED"


def test_skipped_ci_is_blocked():
    assert classify(general_ci="skipped", synthetic_ci="success",
        frozen_object_present=True, postgres_attested=True,
        full_e2e_witness=True) == "BLOCKED"


def test_failed_ci_never_passes():
    assert classify(general_ci="failure", synthetic_ci="success",
        frozen_object_present=True, postgres_attested=True,
        full_e2e_witness=True) == "FAIL"


def test_missing_frozen_object_is_blocked():
    assert classify(general_ci="success", synthetic_ci="success",
        frozen_object_present=False, postgres_attested=True,
        full_e2e_witness=True) == "BLOCKED"


def test_missing_pg_attestation_is_blocked():
    assert classify(general_ci="success", synthetic_ci="success",
        frozen_object_present=True, postgres_attested=False,
        full_e2e_witness=True) == "BLOCKED"


def test_transport_only_is_not_full_e2e():
    assert classify(general_ci="success", synthetic_ci="success",
        frozen_object_present=True, postgres_attested=True,
        full_e2e_witness=False) == "BLOCKED"


def test_truthy_string_cannot_fake_pg_attestation():
    assert classify(general_ci="success", synthetic_ci="success",
        frozen_object_present=True, postgres_attested="true",
        full_e2e_witness=True) == "BLOCKED"


def test_truthy_string_cannot_fake_full_e2e():
    assert classify(general_ci="success", synthetic_ci="success",
        frozen_object_present=True, postgres_attested=True,
        full_e2e_witness="PASS") == "BLOCKED"


def test_unknown_ci_state_is_blocked():
    assert classify(general_ci="completed", synthetic_ci="success",
        frozen_object_present=True, postgres_attested=True,
        full_e2e_witness=True) == "BLOCKED"


def test_missing_exact_source_binding_is_blocked():
    assert classify(general_ci="success", synthetic_ci="success",
        frozen_object_present=True, postgres_attested=True,
        full_e2e_witness=True, artifact_inventory_verified=True) == "BLOCKED"


def test_missing_artifact_inventory_is_blocked():
    assert classify(general_ci="success", synthetic_ci="success",
        frozen_object_present=True, postgres_attested=True,
        full_e2e_witness=True, exact_source_bound=True) == "BLOCKED"


def test_unexpected_skips_are_blocked():
    assert classify(general_ci="success", synthetic_ci="success",
        frozen_object_present=True, postgres_attested=True,
        full_e2e_witness=True, exact_source_bound=True,
        unexpected_skips=1, artifact_inventory_verified=True) == "BLOCKED"
