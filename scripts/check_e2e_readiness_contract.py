"""Standalone fail-closed classification of CI boundary evidence.

No network, subprocess, PostgreSQL or filesystem mutation. This classifier
never upgrades a skipped/queued/failed run to a passing G0.
"""
from __future__ import annotations


def classify(*, general_ci, synthetic_ci, frozen_object_present,
             postgres_attested, full_e2e_witness):
    states = (general_ci, synthetic_ci)
    if any(type(state) is not str for state in states):
        return "BLOCKED"
    if any(state == "failure" for state in states):
        return "FAIL"
    if any(state != "success" for state in states):
        return "BLOCKED"
    if frozen_object_present is not True or postgres_attested is not True:
        return "BLOCKED"
    if full_e2e_witness is not True:
        return "BLOCKED"
    return "PASS"
