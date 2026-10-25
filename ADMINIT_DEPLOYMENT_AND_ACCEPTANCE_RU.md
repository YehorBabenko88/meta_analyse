# Интеграция и приёмка ADMINIT — краткое заключение

Подготовлена отдельная интеграционная ветка от exact PR43. Исходные PR не изменены. Windows/SCM сохраняет FAIL_CLOSED, authorization NONE, exit1 и прежние VERIFIED predicates. PostgreSQL PlanOnly/attestation/DSN guards и checkpoint witness проверяются только на fake connections; реальный кластер/DDL/DML не запускались. Bybit probe различает TRANSPORT_PASS и полноценную E2E-приёмку, сохраняет epoch/snapshot/UNVERIFIED и cooperative drain. Ни public Bybit network, ни Desktop на ADMINIT здесь не запускались.

Ниже приведены происхождение изменений, preconditions G0–G5, бюджеты, stop conditions, evidence capture и rollback ownership. Все этапы требуют отдельного допуска; evidence evaluator ничего не запускает и не выдаёт authorization. Exact final SHA/tree, JUnit и ссылки actual Actions фиксируются в accompanying dated report после commit. Без hosted evidence интеграция не готова. Физические CPU/RAM/disk, PostgreSQL, network и UI результаты остаются BLOCKED/NOT_RUN. **G0 FAIL_CLOSED; ADMINIT/G1 NO-GO.**

# MetaAnalyse ADMINIT — integration and staged acceptance

## Scope and status

This is an isolated Draft integration preparation branch, never a production deployment. Source base: PR43 a04f132d64db0981ef93de1be8208612de08a194, tree d9b0c63525bb8bc28464002e676caee5a5ce626e. Final candidate SHA/tree, local JUnit and actual Actions run links are recorded in the accompanying dated acceptance report after commit. Old-SHA CI does not attest the new tree.

Operator reports Windows11Pro, Python3.12.10, PostgreSQL18.1 existing5432, formerly free55480, MetaScalp1.0.291 API, PR40 physical R0–R5 seven unresolved assessments. These are operator-reported observations, not fresh attestations by this integration. Prior claims of270/315 synthetic PASS must be reconciled with actual JUnit: earlier local receipts included capability skips; this document never converts skips or QUEUED to PASS.

**G0 remains FAIL_CLOSED; ADMINIT/G1 NO-GO. No physical command was executed.**

## Selective integration

| Input | Treatment |
|---|---|
| PR30 privacy /31 native ABI /32 ADMINIT /36 baseline | Already ancestors or selected source-equivalent fixes in43; no mechanical replay |
| PR33 readiness | Reviewed source-only tests/docs; no runtime readiness inferred |
| PR39/40/41/43 | Exact43 base retains aggregate-only fail-closed diagnostic chain and strict contracts |
| PR42 independent SCM oracle | Only missing independent tests ported; oracle additionally compares actual adapter output, malformed data stays UNAVAILABLE |
| PR34 PostgreSQL | Pure PlanOnly/attestation modules/tests selected; inherited CI excluded |
| PR45 independent PG | Selected connection gate/negative tests, strict identity/role/path fixes; fake transaction double-close corrected |
| PR35 public E2E | Opt-in transport probe/tests selected; no network execution |
| PR46 E2E independent | Only confirmed failure-path requirements retained; toy queue test replaced by actual stream callback overflow witness |
| Independent CI branch | Reports only; no unique code fixes to import |

VERIFIED predicates/process classifier/native collector are unchanged. No protected-process exceptions, PPL bypass, service changes, API keys, orders, registration or enrollment.

## PostgreSQL boundary

PlanOnly executes zero actions, reserves loopback127.0.0.1:55480 and a new path under MetaAnalyseCommissioning, rejects5432/existing overlapping PGDATA/reserved Windows paths. It does not create or claim filesystem ownership. Creation remains behind separate successful G0/operator G1. Existing5432 is never selected by guarded paths.

Independent expected system_identifier, dedicated role/db, exact18.1 version, fixed port/host and least-privilege/current-session/database-owner/no-other-DB-CONNECT predicates precede caller SQL. New private connection context freshly attests each connection. Initializer refuses missing identity and wrongDSN before connect; preflight read-only DB connection is guarded too. Approved commissioning Window gets explicit ExpectedCluster into Store; normal noncommissioning Store default is unchanged and outside this guard. No claim that arbitrary application callers are automatically protected.

PG identity/control functions, catalog relations and output types are explicitly pg_catalog qualified; each identity/witness read-only transaction pins SET LOCAL search_path TO pg_catalog before its query. Nonempty PG* environment is refused before guarded connects. This closes source-level search_path/implicit-libpq ambiguity; no real exploit or server SQL validation was run. The system identifier supplied on CLI must come from independently reviewed local G1 evidence, never inferred from the server being checked; this typed value alone is not an authenticated G1 receipt. Existing authorization/enrollment/operator gates remain required and are not generated here.

Read-only checkpoint witness: capture a committed row identity and WAL marker through fresh attestation, then explicitly verify later visibility/flush/redo/checkpoint/timeline. No forced CHECKPOINT, grants, automatic polling or DDL/DML. Permission denial/malformed/wrongcluster/stale marker BLOCKED. OBSERVED describes SQL metadata, not physical disk durability or proof of automatic checkpoint scheduling. Live witness remains BLOCKED.

## Public Bybit and Desktop

Public depth50 snapshot/delta transport only; not full-depth channel. Distinguish immutable snapshot/delta frame kinds and connection epochs. Reject delta before fresh snapshot, duplicate/regressing sequence/update and malformed epoch/health. Increasing numeric skips do not prove packet loss on this channel; complete exchange continuity remains unverified. Reference: https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook

Real callback QueueFull witness proves existing stream invalidates books/reconnects; gap handler must drain any consumer queue containing already published snapshots. Transport's bounded websocket queue uses backpressure; immutable snapshots cannot be retroactively revoked. Fresh snapshot is required after reconnect. Actual health monitor with fake clock proves UNVERIFIED/STALE handling and provisional recovery, not rendered physical UI.

Probe emits TRANSPORT_PASS only with current-epoch per-symbol snapshots and no detected faults/budget exhaustion. It cannot emit full DB/Desktop E2E PASS. Thread/task sampling is bounded and configurable, but CPU/RSS/disk metrics are not thereby measured. Stream shutdown is cooperative: deadline requests cancellation and records BLOCKED while retaining ownership until drain finishes; cancellation-resistant code can remain pending. No hard stop/forced thread termination guarantee.

Existing fake-store tests prove committed observation identity and commit-before-telemetry/rollback/no-early-drain-release. They do not prove a real PostgreSQL checkpoint, crash durability, exchange completeness or physical Qt responsiveness.

## CI and evidence

Integration-only Windows/Linux Python3.12 workflow checks exact PR head, frozen predicate oracle, pinned deps, all selected synthetic regressions, complete source-collected hashed JUnit identities/statuses plus minimum count and critical roots. Only two exact source-collected symlink capability skips are permitted; they remain BLOCKED capabilities. Two live-DPAPI cases explicitly deselected. Raw JUnit/logs remain local; strict publisher emits only minimal source/run-bound public artifacts. Final API review must bind run/attempt/job/branch/source SHA/tree, ZIP SHA256, manifest inventory and full testcase identities. QUEUED/SKIPPED/absent artifacts never PASS.

Synthetic plugin is scoped tripwire instrumentation for reviewed tests, not a process/OS security sandbox. It patches selected DB/native/socket APIs and restricts child executable basenames; fixtures begin after imports and alternate APIs/children are not universally contained. Selected tests/children were source reviewed; no native/realDB/externalBybit operations were found or performed. This limitation must not be presented as comprehensive containment.

GPT3 collaboration was requested in existing meta_3 chat; actual tool-accessible reply body was an unresolved content reference. Do not treat that as independent CI approval. A separate CI reviewer inspected workflows/API metadata and found no queue root cause; final hosted evidence is still required.

## G0–G5 preconditions, budgets and stop rules

`commissioning/stage_acceptance.py` is a pure submitted-evidence evaluator; it performs no probes/install/start/rollback, returns authorization NONE and next_stage_started false even when fields satisfy PASS. It cannot authenticate externally supplied receipts. Exact SHA/tree must match in every submitted stage and predecessor record. Missing/malformed/NaN/bool/source mismatch => BLOCKED; known refusal => FAIL. A PASS result is evidence checking, never permission to advance.

Provisional conservative budgets: CPU peak<=80%, private memory delta<=1024MiB, free disk>=8192MiB; runtime queue<=1024, UI age<=5s, active writes0 at final drain. These values require operator review against real baselines; no measurements are fabricated. Measurement absence blocks acceptance. Duration minima G3=1800s/G4=7200s/G5=86400s; allow30s final drain, then FAIL budget but retain ownership of writes. No forced kill.

| Stage | Preconditions/evidence | Time/budgets | Stop/rollback |
|---|---|---|---|
| G0 | Exact clean source, hostedCI, host/process/SCM identities complete; unresolved0 | max300s plus common budgets | Any unknown/refusal => STOP; retain private local evidence, no enrollment/G1 |
| G1 | G0 PASS same source + separate operator approval; isolation/cluster/role/migration/rollback ownership proof | max1800s common budgets | No5432; stop only owned new cluster, cleanup only exact ownership attested, never automatic recursive delete |
| G2 | G1 PASS + separate approval; publicBybit sequence/DBcheckpoint/Desktop/shutdown evidence | max600s runtime budgets | Invalidate on gap/overflow/stale/DBerror; graceful stop/drain, retain failed evidence, no continuation |
| G3 | G2 PASS + separate approval; continuity/resources/privacy/checkpoint/drain evidence | >=30min <=30min30s | Stop on any breach, graceful drain; no automatic G4 |
| G4 | G3 PASS same source + separate approval, same witnesses | >=2h <=2h30s | Same; no automatic G5 |
| G5 | G4 PASS same source + separate approval, same witnesses | >=24h <=24h30s | Same; no production approval inferred |

Evidence is local-only unless a separate privacy review approves publication: timestamps, host/process/service/DB identity and resource traces may be private. Public summaries must use allowlisted enums/counters and source code SHA/tree, never raw DSN/account/PID/path/hostname/tokens/errors. No writes to Norton/Defender/firewall/ACL/registry/services/Grid or existing applications.

## Next G0 — prepared, never automatically run

After exact final candidate source review and actual hosted evidence acceptance, operator selects one approved read-only invocation, using existing approved Python3.12/PowerShell effective policy, a clean exact Git checkout and a new local output outside checkout. No ExecutionPolicy Bypass/auto-elevation/new API probe.

```powershell
python -B .\commissioning\native_scm_diagnostic.py --expected-sha <APPROVED_FINAL_SHA> --expected-tree <APPROVED_FINAL_TREE> --output <NEW_LOCAL_JSON_OUTSIDE_CHECKOUT>
$diagnosticExit = $LASTEXITCODE
```

Expected exit1/FAIL_CLOSED/authorization NONE, even with available projection. Review co-occurrence without exposing member names. Do not rerun automatically, relax contracts or proceed to G1. This diagnostic invocation is not full host/CI/source G0 PASS; external source/host attestation and complete identities remain independent prerequisites. CPU/RAM/disk/PostgreSQL attestation/Bybit network and physical UI results remain NOT_RUN/BLOCKED until explicitly admitted.

Remaining blockers include exact hosted artifacts, unresolved process/SCM identity, PPL/module access within allowed rights, actual native ABI, private PG system_identifier/G1 ownership and SQL/server behavior, checkpoint persistence, public network/physical UI/resources/duration witnesses. Source synthetic PASS never closes these blockers.
