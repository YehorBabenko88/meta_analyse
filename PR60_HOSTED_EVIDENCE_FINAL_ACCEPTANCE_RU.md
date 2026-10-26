# PR60_HOSTED_EVIDENCE_FINAL_ACCEPTANCE_RU

Дата 2026-10-26. Независимый Security/Provenance audit, **read-only** PR #60. HEAD `0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30`, tree `a85846d46df6e95f3d757e25399d991ee1db872b` независимо сверены с Git commit API. Draft PR, без merge/deployment.

## Матрица первоначальных 11 hosted runs

Push: CI `40399548345` (3 jobs), Commissioning PostgreSQL18 `40399548456` (1), ADMINIT final integration `40399548254` (3), Kernel offline `40399548264` (2), Public JUnit `40399548316` (2), Native SCM `40399548266` (2). PR: CI `40399605883` (3), ADMINIT final `40399605857` (3), Kernel offline `40399605833` (2), Public JUnit `40399605895` (2), Native SCM `40399605937` (2). **11 SUCCESS / 25 completed-success jobs**, all original run attempts 1.

Additional same-SHA push runs `40403514742`, `40403514467`, `40403522738`, `40403522687`, `40403560778`, `40403560773` were QUEUED at inspection, not part of initial 11-run acceptance. These are not PASS and require independent scheduling/event analysis; do not blend with original run attempts.

## All 29 real ZIP digests and uploader job identities

All 29 original ZIPs downloaded from GitHub artifact IDs. Local SHA256 of raw ZIP bytes independently equals authenticated GitHub API `digest` for every entry. No duplicate/path traversal ZIP entries. `manifest.files` exactly matches ZIP inventory excluding manifest, each file SHA256 matches. Manifest source SHA/tree/run ID/attempt=1/job matches corresponding API run and job name; job name is the manifest-reported uploader identity, while a separate direct uploader step-log correlation is **not yet independently complete**.

| Run ID | Manifest job | Artifact ID | ZIP SHA256 |
|---|---|---:|---|
| 40399548345 | archive-pinned-contract | 12689566734 | `014460091f4bb81b604d769b3d9e0c18a84ea95ce256fb28b93dfe29f28aeec1` |
| 40399548345 | linux | 12688643054 | `afc65e90d4fee9d5eff50b50de0884799a40dcc4b243a3e2d7620fcff7702dd2` |
| 40399548345 | linux | 12688603049 | `4ef41a5181e98115b1a8f277df6f067a7a0233e83711c3a86f6eff5e66fa37f4` |
| 40399548345 | windows | 12688063918 | `bcd372c7ec171493cd3d0ae70ba0d7278e92482a52428739c82c40023a899f8e` |
| 40399548345 | windows | 12687619762 | `648e19aab6919721671f8ab8ecf9b01ba74b4ac4134667328d629d1728e7cdeb` |
| 40399548456 | postgres18-linux | 12689551074 | `8146b68c14eb4982310584545a7c7248986ba14c2146cfb9c9640ad74505ea03` |
| 40399548254 | disposable-postgres18 | 12688757310 | `f47ba9d9b0c0c2adf4b7ea038d1b8b5bde3a6ef3e07ec59bc5680fe6784f50fd` |
| 40399548254 | synthetic | 12688671604 | `b7864fea9042a5c07844175e82bb0384550ec96a9009258bfdeee8f694b7dcba` |
| 40399548254 | synthetic | 12688532127 | `ecc1647b814188a14f0418e79e1c103cfd4d84298a6db049a225a9920e2ce44b` |
| 40399548264 | synthetic | 12687988359 | `01c1323034a30c68af5109320aa69a732c8e8c11ec5e19a0a4e80232d41753c2` |
| 40399548264 | synthetic | 12687983317 | `249691538d471cafa6be621bee6711f61528d9b8ca0e84c7a3bd1a731df466d9` |
| 40399548316 | offline | 12688911202 | `a4c22eaa7219fb5e86296c19cd75a8ad512f14b959b1d088a565b0643393c131` |
| 40399548316 | offline | 12688237530 | `77cb399e9cadd3a731b02c498d92624f319c5d0e6d72096b1c08e916d5d73ae5` |
| 40399548266 | synthetic | 12689341405 | `5d92c6b1a5a7bd356bb02f0bc4d41f912bac14282f0b22fcfc7596e49b8ce638` |
| 40399548266 | synthetic | 12688716956 | `af08b065c097af508f7eaa90165c9c6944fe38f380c936e9f12af968111b9f2c` |
| 40399605883 | linux | 12689336811 | `e22b738223ce6958370de4dd899e485a4399792e9292de3562ecd304089d3f97` |
| 40399605883 | linux | 12689072070 | `e6562cb52e2a1d40e0abc85bf36f31b2b98b332ddd6c8d033359b90fc25b4bcf` |
| 40399605883 | windows | 12687899121 | `373d7da76599e91bb2b4b4d46bea421371ed6aefd26a77b288de9c5b6660f02c` |
| 40399605883 | windows | 12687874087 | `22bbd4a14818687c67f630368144ac88023d3ba4fb052a67e92cb186c282ddc7` |
| 40399605883 | archive-pinned-contract | 12687639648 | `87eab574c8dc7bac41ea9c115999c34b6f952cde95f7b7de83faf855a87115d8` |
| 40399605857 | disposable-postgres18 | 12689328010 | `d74b3fa889a6ab484403c6bebff882e03fc6544917eb13b47e0c994bdaedb272` |
| 40399605857 | synthetic | 12689196416 | `f6bde056802b538e0a6cb7c6947da971f523bbc0fc459b9bdf813027d1d0f048` |
| 40399605857 | synthetic | 12688079038 | `de445974cf080bbd694a3909b32ba53f226cbaf5dce874957a5510d1d75b8a61` |
| 40399605833 | synthetic | 12688827382 | `4f47da36508a5ded85bff87d20ede44a2ba0000d5a3ed2b1ddd663eb21249269` |
| 40399605833 | synthetic | 12688507841 | `fd6b4aa5b24dad65fb76d81405fafe864b7a86f61ca91f8ae832e9cfd8b45687` |
| 40399605895 | offline | 12687674334 | `a03c071f0a03ee242640a73333707ebe9be6db27b08ce3edf714ec9b3c40d4a7` |
| 40399605895 | offline | 12687594441 | `2d73ef89adcd52cace68758478953fc343997e44e03e96cec1a9c51529ce9e2a` |
| 40399605937 | synthetic | 12689036517 | `a1512b554ffc89c1f337c5e71c990693d4b70dd3203c84e299623c2fb40f9c77` |
| 40399605937 | synthetic | 12688267869 | `c37a1a2bb2c1531ec92c02e1a5dab6adcc52a015afde1ae328c2a597bcc26bb4` |

## JUnit independent public artifact inspection

Full CI Windows: `junit-001.xml` **2543 cases, 0 fail/error/skip** in both push and PR. Linux: `junit-001.xml` **2543 cases, 0 fail/error, 1 skipped** (2542 PASS), push and PR. Diagnostic JUnit `junit-000.xml`: 400 cases, no failure/skip. Ten lifecycle XMLs: 67 cases each, no failure/skip. Combined full-CI evidence: 3613 testcase instances per ZIP (includes diagnostic + repeated lifecycle, **not** 3613 distinct baseline tests). Commissioning PG18 Linux evidence includes 2543 full cases (1 skip) plus ten lifecycle 67-case repeats. Selected ADMINIT synthetic: 1893 cases per Windows/Linux, no failures/skips; disposable PG18.1 4 cases each, no failures/skips. Kernel identity 948, Native SCM 338, Public JUnit 90 per OS/run, no failures/skips. Archive pinned 8 cases per run.

Published testcase names use `case_<SHA256>` format. Counts/status/uniqueness inspected; **full independent raw-name to opaque-identity mapping is not recoverable from published artifacts**. The exact required-test identity gates succeeded in CI, but raw private JUnit and source collection are not independently reproduced here.

## Privacy and UI benchmark

All 29 ZIPs passed bounded privacy marker inspection: no `<properties>`, `<system-out>`, `<system-err>`, `hostname=`, obvious DSN/password/token/traceback markers in public JUnit; no raw paths in checked projected content. Source/manifest contain only expected bounded metadata. This is not an assertion that every raw GitHub Actions job log is privacy-clean.

Four `ui-benchmark.json` files exist (push/PR × Windows/Linux); schema keys include `schema_version`, `status`, `reason`, `render_samples`, `render_fps`, heartbeat/render/CPU/Python-heap metrics, `diagnostics`, `worker_stopped`, `loop_closed`. All four have `status=PASS`, `loop_closed=true`, bounded counters with `async_errors=0`, `ui_errors=0`, `thread_violations=0`, `stamp_overflow=0`. Benchmark manifests bind source/run/job; metrics are synthetic Qt/offscreen, not physical FPS or RSS. Failure-path negative tests reported hosted SUCCESS, but independent failure-path publication with intentionally failing pytest is not verified here.

## Severity and acceptance

- **P0 PASS (bounded original runs):** 11 terminal SUCCESS, 25 jobs SUCCESS, exact SHA/tree, 29 downloaded ZIP SHA256, inventory/provenance, no JUnit failures/unexpected skips.
- **P1 PASS (bounded public artifacts):** 4 UI benchmark evidence, projected JUnit privacy, PostgreSQL 18.1 receipts and 4-case disposable jobs.
- **P1 OPEN:** independently correlate each artifact ID with concrete upload step log; independent raw-to-opaque identity oracle; raw Actions log privacy and hosted failure-path witness.
- **P2 OPEN:** six later queued same-SHA runs must not be presented as SUCCESS; clarify event/concurrency scheduling without guessing billing/quota. Legacy source revisions must not be mixed.
- **ADMINIT physical G1 / deployment: NO-GO.** No physical testing or production DB changes.

**Verdict: BOUNDED HOSTED EVIDENCE PASS for initial 11 runs, full independent security acceptance remains BLOCKED on outstanding log/identity/failure-path proofs.**
