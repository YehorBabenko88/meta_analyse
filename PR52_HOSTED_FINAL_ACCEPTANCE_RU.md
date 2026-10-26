# PR52_HOSTED_FINAL_ACCEPTANCE_RU

Дата: 2026-10-26. Независимая read-only hosted acceptance. **Корректный репозиторий — `YehorBabenko88/meta_analyse`, не `YehorBabenko88/math`.** Предыдущее заключение в math о SOURCE/RUN ID mismatch относится к ошибочному выбору репозитория и не применимо к этому кандидату.

## Exact candidate

Draft PR #52 `YehorBabenko88/meta_analyse`, HEAD `8a1c20184cbd878097f62530fc07630568fb7f84`, tree `334df27319ce37fe562b6195b255742dae6db8c8`. Оба run objects совпадают по head SHA/tree, `run_attempt=1`. Push `40295973256`, PR `40295979565`: terminal SUCCESS. Каждая из шести jobs terminal SUCCESS, включая required source, identity, privacy and publication steps.

## Independently downloaded artifacts

| Run | Job | Artifact ID | ZIP SHA256 |
|---|---|---:|---|
| Push 40295973256 | synthetic Ubuntu | 12638510930 | `4b78e324b1e67c6cd88af1145f14232a38f80feb0898fc8f82c3bf3b4fd1d748` |
| Push | synthetic Windows | 12638491012 | `61dab7b5f366f426cd9ba3210d37eb9ad0c9922eacb3d8c7d8b81f6136d02194` |
| Push | disposable-postgres18 | 12638077494 | `9051ca56ee57ce403ac0dcb2d2f15953aa508118e7f0c726f2edfaf6101a0e12` |
| PR 40295979565 | synthetic Ubuntu | 12638475826 | `2bf18553a187cc4367bbfae0ad341ebde9d44cb6e4ad4a87264b139f2fbb7db4` |
| PR | synthetic Windows | 12638580979 | `af23dad5e4a31edfa32c7ddc97e5adaf7e1674368cee7ceeacec70af16d32c5c` |
| PR | disposable-postgres18 | 12638665848 | `65456ec3673cf6ccdb69d4e9f2587af93fdb7cce5756b084a782cd2a2af10236` |

All six ZIPs downloaded from GitHub artifact IDs; local SHA256 matches GitHub API digest. No duplicate filenames; exact ZIP inventory matches `manifest.files` plus `manifest.json`; every file SHA256 matches manifest. All source receipts and manifest provenance bind to exact SHA/tree/run ID/attempt 1/job. PR event SHA is merge-event SHA `d36b8806bb5de02b122649a607075a4b17dd8718`, correctly distinct from checked-out PR head.

## JUnit and privacy

Four synthetic ZIPs: **1744 testcase each**, 0 failure, 0 error, 0 skipped. Two disposable PostgreSQL ZIPs: **4 testcase each**, 0 failure, 0 error, 0 skipped. Typed PostgreSQL receipts both state `server_version=180001` (18.1). All six projected JUnit files use `public.tests` and unique `case_<SHA256>` identities, with no extra XML elements beyond testsuites/testsuite/testcase. Byte inspection found no typical raw hostname, system-out/err, properties, traceback, runner paths, PostgreSQL DSN, password/token strings or SID markers. This is a bounded check of the six public artifacts, not proof that raw Actions logs are privacy-clean.

The hosted `Exact complete source-collected JUnit identity and status gate` and `check_integration_junit.py` steps completed SUCCESS on Windows and Ubuntu. However, original raw JUnit and source-collected identity mapping are deliberately not in public artifacts; a fully **independent raw-to-source identity oracle** cannot be reconstructed solely from the published opaque JUnit. We accept the hosted identity gate execution plus exact public counts, not an independent raw identity comparison.

No legacy policy-SKIPPED workflow is promoted to PASS. No live-DPAPI deselected cases are counted as PASS. No evidence of physical ADMINIT G1: disposable hosted PostgreSQL 18.1 is not physical target attestation.

## P0/P1/P2 verdict

- **P0 PASS (bounded hosted CI):** exact candidate SHA/tree, two run attempts, six terminal-success jobs, six downloaded ZIPs, 1744 projected PASS on each synthetic job and 4 projected PASS on each disposable PG job.
- **P1 PASS (bounded public evidence):** ZIP digests, manifests, exact inventory, source/run/attempt/job binding, no identified sensitive strings in projected XML, PG 18.1 typed receipt.
- **P1 OPEN:** independently inspect raw Actions logs and private raw JUnit/source identity mapping; failure-path privacy publication not exercised by these successful runs.
- **P2 OPEN:** negative hosted adversarial mutation/failed test evidence, all legacy workflow policy skips, historical artifacts and low-entropy identity pseudonym risks.
- **Physical ADMINIT G1 / production: NO-GO**, not authorized by hosted disposable PostgreSQL.

**Overall verdict: HOSTED EVIDENCE PASS (bounded) / FULL SECURITY ACCEPTANCE BLOCKED on independent raw-JUnit oracle and failure-path; PHYSICAL NO-GO.** No reruns, merge, deployment or physical/production DB operations.
