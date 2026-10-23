# CI metadata boundary audit — 2026-10-23

Audited source: PR25 `0bdc6bd463e4252a92cc71a403af3ddfcd56cff2`, tree `08a8cce927e5620fb2bb4f9eb5e08c35de5ccfab`, based on PR24 `95bb4efc635fa3ddee6c8a95b43ba9a3040fffbb`, tree `317f56c198145ee9744bf5b12c7d93df126a0e4d`. Source PRs remain unchanged. This follow-up changes only CI metadata admission, tests and branch policy; it does not repair GitHub runner infrastructure or authorize physical work.

## Confirmed defects

- P1: `--require-gate` accepted a completed/success run without job or artifact receipts. A successful workflow roll-up does not establish execution of required jobs or presence of required artifacts. Original eight tests passed; eleven new negative cases failed before the fix.
- P1: the maintenance branch of PR25 is absent from identity-only exclusions. Its CI run can select Windows native probe/live DPAPI and disposable PostgreSQL jobs. New and PR25 maintenance branches are now excluded at job level; this does not cancel/rewrite existing queued runs.
- P2: malformed latest run identifiers were sorted below older successes; conflicting duplicate run attempts, wrong workflow path, duplicate JSON keys and NaN were accepted. Selection now rejects malformed/duplicate attempt identities and checks workflow path. JSON parsing is unambiguous and finite.
- P2: an explicitly required Commissioning PostgreSQL18/pull_request gate is incompatible with its push-only workflow. The CLI rejects this configuration, without treating every absent branch/path-filtered workflow as a failure automatically.
- P1: after the queues drained, both PR25 full CI runs failed collection with ModuleNotFoundError/hypothesis on both OSes. The property suite imports Hypothesis, but the standard test extra and requirements.lock omitted it. This follow-up adds the existing synthetic pin to the test extra/lock and verifies property test collection without executing host/database tests. Privacy failures following incomplete collection are not bypassed or relabeled PASS.

## Queue facts and limits

Observed through GitHub REST, not inferred from branch conditions: PR25 CI runs [39921648688](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39921648688) and [39921655884](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39921655884) were queued, with three jobs each and no assigned runners/steps. PR24 synthetic runs [39918425152](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39918425152) and [39918431105](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39918431105) were queued; Windows in the push run subsequently completed at 08:24:06 UTC, while Linux was still queued. Whole-run status therefore must not replace per-job evidence.

Actions enabled/all actions allowed, default token contents permissions read, no environments or pending deployments, standard ubuntu-latest/windows-latest labels, no configured workflow/job concurrency or max-parallel in the four candidate workflows. No repository runs were returned by the in_progress query at that snapshot; this does not enumerate account-wide concurrency across other repositories. No self-hosted runners were registered; these jobs do not request self-hosted labels. GitHub Status reported Actions operational/no active incidents at observation time; that does not exclude earlier or unreported regional issues. Billing endpoint returned 404 and reported missing user scope. **The underlying scheduling reason is not exposed by the available evidence. Billing/quota/account-wide capacity is UNVERIFIED, not a diagnosed root cause.** No settings, billing scopes, runner labels or source PR runs were changed.

Subsequent snapshot: both PR24 synthetic runs completed success; both PR25 full CI runs completed failure. Runner assignment resumed without changing these runs/settings. PR25 collection failure is proven, while the earlier scheduling delay remains unexplained. Existing PR25 runs were created before this audit; this audit neither dispatched nor reran their native/database jobs.

## Workflow matrix at the pinned candidates

All six workflows returned by GitHub registry were inspected, including historical branch-only workflows absent from candidate trees.

| Workflow | Triggers and branch/path policy | Runner/jobs | Permission/concurrency/environment | Candidate interpretation |
|---|---|---|---|---|
| CI | push + pull_request; three identical branch-exclusion job predicates | Windows, Linux, archive Ubuntu; native/DPAPI/PG in full CI | contents read; no concurrency/environment | #24 jobs skipped; #25 queued and unsafe for synthetic-only scope |
| Kernel identity offline | push to seven identity branches; PR identity-specific paths | Windows/Linux synthetic matrix | contents read; no concurrency/environment/max-parallel; default fail-fast | #24 queued/partial Windows success; #25 NOT_RUN because triggers do not match its three-file diff |
| Storage ingestion integration | PR storage/commissioning paths; push storage/audit branches plus paths; same exclusion predicate | Ubuntu with PG18 service | contents read; no concurrency/environment | #24 skipped on triggered PR; #25 NOT_RUN for its diff |
| Commissioning PostgreSQL18 | push audit/** only | Ubuntu PG18 service | contents read; no concurrency/environment | NOT_RUN for both; PR is incompatible |
| Independent integration audit V2 | historical `9e6ce6baf60caae2a29e56b4f5716f59d78cca4a`, push audit/parallel-integration-v2-20261019 and audit_v2/workflow paths | Ubuntu PG17.6 | contents read; no concurrency/environment | absent from candidate trees; not a candidate gate |
| Independent PR18 exact-SHA acceptance | historical `c88052c444d67e3d9370eb609ae27d9c64a0936a`, push one audit branch or workflow_dispatch | synthetic, controls, full OS, storage, archive, native | contents read; no concurrency/environment; synthetic fail-fast false | explicitly checks out PR18, not #24/#25; never transfer success |

Historical source files were read only; their pipelines have additional legacy risks (raw logs/JUnit upload and historical `pytest | tee` without pipefail in audit V2). They were not enabled or changed by this fix and are not accepted for current evidence.

The follow-up adds **CI audit synthetic**: exact maintenance branch push, selected PR paths plus exact job-level head-branch guard; Windows/Linux, max-parallel 2, fail-fast false, timeout 10 minutes, contents read, event-separated concurrency group with cancellation only within this new workflow. It installs pytest/Hypothesis only and uses `--noconftest`; no application, PG, Qt, native probe, live DPAPI or physical collection is invoked. Property test collection verifies the dependency without running the suite. Artifact upload follows strict existing JUnit projection and privacy gate, missing files are errors. Existing kernel/native/PG trigger lists are unchanged.

## Gate contract

Default inventory CLI exit0 means INVENTORY_ONLY, never acceptance. Explicit --require-gate can PASS only for RUN_JOB_ARTIFACT_METADATA_ONLY scope. This is **not** JUnit/content/privacy acceptance, proof of authenticity of a user-supplied JSON export, or a physical readiness decision.

An API export can remain a bare workflow_runs list/wrapper for status inventory, but successful runs without receipts are BLOCKED. To verify a gate, supply:

```json
{
  "workflow_runs": ["complete GitHub run objects"],
  "run_evidence": {
    "123": {
      "run_attempt": 1,
      "jobs": {"total_count": 3, "jobs": ["complete job objects"]},
      "artifacts": {"total_count": 3, "artifacts": ["complete artifact objects"]}
    }
  }
}
```

The quoted strings above describe objects, not valid test receipts. Fetch run-specific attempt jobs (`/actions/runs/ID/attempts/N/jobs`), run artifacts, and all pages, and preserve actual total_count. Job identity includes run_id/head_sha/run_attempt and exact required job names. All returned jobs must complete successfully; extra/skipped/queued/cancelled jobs block. Artifacts must have unique identities, required exact names, positive size, expired=false, bound workflow_run.id/head_sha, and created_at at or after run_started_at for the selected attempt. Missing timestamps or stale prior-attempt artifacts block. Artifact content must still be independently downloaded/verified against source/JUnit/privacy manifests; metadata can be misleading or incomplete. Partial reruns with mixed-attempt jobs can be conservatively BLOCKED; do not substitute old success receipts or delete artifacts automatically.

```powershell
python scripts/audit_workflow_run_states.py --runs-json receipts.json --sha <full-lowercase-40-sha>
python scripts/audit_workflow_run_states.py --runs-json receipts.json --sha <full-lowercase-40-sha> --require-gate 'CI audit synthetic:push'
python -m pytest --noconftest -q tests/test_workflow_run_states.py tests/test_workflow_run_states_adversarial.py tests/test_ci_audit_workflow_policy.py --junitxml=<private-scratch>/ci-audit.xml
```

Repeated branch exclusions are compacted to a shared logical form per job; truth-table tests assert all four copies have identical lists and preserve all seven original exclusions in actual push/PR contexts, adding only the two maintenance branches. Cross-file YAML anchors are not used, and no runner-allocated policy job is introduced. Further centralization into reusable workflows is a separate change, not needed to repair these predicates.

Local validation: 83 synthetic tests passed before the dependency-fix commit, no skipped cases, strict JUnit projection/privacy passed, Python compile and git diff checks passed. The dependency-specific test was red before the manifest/lock fix. actionlint 1.7.12 validates all five current workflow files (shellcheck/pyflakes disabled); downloaded official Windows archive SHA256 `6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9` matches release checksum. Intermediate commit a252aac passed both hosted events, four suites of 82; that evidence does not transfer to the subsequent dependency-fix SHA. Inspect exact final follow-up SHA/run receipts in the external acceptance report.

**PR25 source gate acceptance FAIL; repaired metadata predicates locally PASS; exact-candidate hosted execution remains independently gated. ADMINIT NO-GO.** No merge/deployment or production/system configuration changes.
