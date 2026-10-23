# CI artifact content acceptance — isolated offline gate

This follow-up is based on exact PR #26 HEAD `8885381efa5c65741ae765f55bc230baccbc0ccc`. No existing PR is changed. It adds an offline content check only; no new native/PG/physical workflows are enabled.

## Inputs and custody

Obtain the two named artifacts from each of the *two* exact-SHA GitHub runs (push and pull_request). Verify their GitHub run IDs, run attempts, jobs, artifacts and SHA using the existing metadata auditor and authenticated API responses **before** extracting. Extract into four separate directories, each containing only `ci-audit.xml` and `source-sha.json`. Do not combine files from distinct runs, attempts, or candidates.

Example:

```sh
python scripts/verify_ci_audit_artifact_contents.py --sha 8885381efa5c65741ae765f55bc230baccbc0ccc --tree a28f5e17c94ddc7d1ad8bfb3e73e7f6423ecf3c7 --push-windows extracted/push-windows --push-ubuntu extracted/push-ubuntu --pull-request-windows extracted/pr-windows --pull-request-ubuntu extracted/pr-ubuntu
```

The content gate checks exact SHA/tree/event, projected JUnit structure, at least 83 tests per cell, no failures/errors/skips, no duplicate test identities, and exact cross-platform/cross-event identity equality. It fails closed on missing, unexpected, symlink or malformed files.

**Limitations:** This check does not fetch or authenticate GitHub API receipts, bind artifact content cryptographically to a run attempt, verify test semantics, authorize deployment, or prove native/PG/physical readiness. A malicious actor able to forge all four input directories could fabricate a content PASS. Maintain authenticated custody separately. ADMINIT stays NO-GO.

## Follow-up

Independent reviewer must verify content from the exact hosted artifacts and test negatives. Until then, gate implementation is **UNVERIFIED**, not PASS. Do not merge this Draft PR or earlier PRs automatically.
