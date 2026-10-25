# SCM correlation: bounded design and acceptance

Base: exact PR41 5b622cc218fdf90d26164d544176dd647297fc53. One additive `type_cooccurrence` map under each existing configuration phase, containing all five fixed keys BOTH_FAILED/REGISTRY_ONLY_FAILED/SCM_ONLY_FAILED/NEITHER_FAILED/NOT_EVALUATED. Unit: reviewed service member per snapshot phase, only the same unresolved-process population as existing configuration counters. Unknown service rules are not counted as reviewed contracts.

Use the already computed `service_host_configuration_checks()` results. No additional classification/native collection, contract changes or authorization. NOT_EVALUATED means missing/incomplete configuration or unsuccessful/incomplete SCM coverage, not NEITHER_FAILED. Evaluated helper results must be exact bools. Existing strict field/lifetime/source validation is retained. For reviewed members require paired membership/config consistency (order independent membership); malformed fields, changed membership/config or one-sided evidence fail the entire projection. Matching incomplete evidence may remain NOT_EVALUATED. Missing mandatory fields do not default to PASS.

Before and after counters are separate correlated snapshots, never summed as distinct services. Exact source before/finally checks remain in CLI. Always FAIL_CLOSED/authorization NONE/exit1. Existing diagnostics schema stays additive (schema1), no new parameters or physical runs.

Tests first: one member with two failures vs two distinct members, all categories, incomplete/missing config, strict malformed fields, duplicates, pair changes, source/lifetime regressions, order and reassignment privacy, host failure clears partial output. Then minimal implementation, source review, Windows local synthetic JUnit/privacy identities, exact-SHA Windows/Linux hosted workflow and independent artifact checks when available.

Privacy: no individual records/labels/IDs/types/accounts/paths. Permuting indistinguishable member assignments can preserve the public projection; tests demonstrate non-unique inverse for synthetic data. This is not general anonymity: five known contracts, rare counts, external knowledge and repeated runs can identify/strongly suggest membership. No k-anonymity/differential privacy/statistical unlinkability claim; default local-only and no auto-upload of host diagnostics. Co-occurrence intentionally adds joint information. Even NEITHER_FAILED concerns only two type predicates, not admission or all service proofs.

## Интерпретация для пяти evaluated members

| Схема | BOTH_FAILED | REGISTRY_ONLY_FAILED | SCM_ONLY_FAILED | NEITHER_FAILED | NOT_EVALUATED |
|---|---:|---:|---:|---:|---:|
| Один member с обоими type refusals |1|0|0|4|0|
| Два members с отдельными type refusals |0|1|1|3|0|

Это условные примеры, не результат нового ADMINIT запуска. Сумма bucket counts равна member_checks в данной фазе. NEITHER_FAILED означает только прохождение двух type checks, не всех восьми config predicates и не service admission. NOT_EVALUATED не означает отсутствие отказа. Per-phase groups не объединяются в longitudinal per-member IDs. Before/after membership/config inconsistency делает всю projection UNAVAILABLE, без partial counters.

Positive/all-failed/one-sided type controls, missing/incomplete config/SCM, malformed bool/float/None/fields/duplicates, changed paired groups и два CLI all-or-nothing cases включены в tests/test_native_scm_adapter.py. Existing exact SHA/tree/finally binding, PID reuse/lifetime, public privacy и no authorization tests выполняются в том же targeted suite. Frozen old predicate oracle остаётся доступен без изменения classifier.

Red: первые21новых cases на прежней реализации —14FAIL/7PASS. Green после реализации и2CLI cases:338cases=337PASS/1symlink capability skip (Windows local), exit0. Это не Linux/hosted доказательство. Полный reproduction command указан в .github/workflows/native-scm-adapter-synthetic.yml; только synthetic, --noconftest, no native collector/DPAPI/PG. Hosted artifacts должны пройти exact SHA/tree/run/attempt/source receipt, strict JUnit identities/counters/privacy checks; QUEUED/SKIPPED не PASS.

Физическая попытка не выполнялась; существующая процедура one-shot требует отдельного допуска после review. G0 всегда FAIL_CLOSED, authorization NONE, exit1; G1/ADMINIT NO-GO. Crash durability, malicious concurrent writer и source ABA attestation не доказаны и этой добавкой не меняются.
