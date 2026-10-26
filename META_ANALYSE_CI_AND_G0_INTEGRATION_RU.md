# MetaAnalyse — CI remediation и единый кандидат G0, 2026-10-26

## Решение / exact source

Integration branch `integration/final-ci-g0-20261026`, base PR55 `edc8e831c202e3597e27532359ab9c47a9f29a88`. Exact final HEAD/tree, new Draft PR/runs/ZIP and authoritative exact-candidate counts recorded after commit in accompanying dated receipt; base SHA is not new-candidate evidence.

**Source/local synthetic acceptance bounded; hosted acceptance pending; physical ADMINIT/G0 NOT_RUN, authorization NONE, G1 NO-GO.** Original52/53/54/55 branches unchanged. No merge/deployment/system/security/PG5432/MetaScalp actions.

## Inputs/ancestry

| PR | Verified HEAD | Tree | Integration |
|---|---|---|---|
|52|8a1c20184cbd878097f62530fc07630568fb7f84|334df27319ce37fe562b6195b255742dae6db8c8|Ancestor54/55|
|53|bbbc1cc75f9bb15490867227396267ba81eaf9b0|2fd6f9454f167b1903712fadb6e3f508edbef043|One historical audit doc only; merge-base with55=52; copied exact bytes under docs/reviews, no inherited approval|
|54|0883a979ba364a778a3ca78d0dc4fdc5026e46d7|b10b07c888e8fd3e95c97ed5945479cde7196b5a|Ancestor55; strict HTTP parser + format-only observer retained|
|55|edc8e831c202e3597e27532359ab9c47a9f29a88|84e128ca44e2ffe54bda7c003d0358a0b8d8b8fd|New branch base; encoding tests/PS5.1 checker retained|

No production src/commissioning changes in this remediation. New fixture/plugin/bootstrap/oracle/CI/docs only. Independent53 doc describes old52 evidence and remains explicitly historical. Actual old full-CI runs on audit branch at52 SHA failed despite selected synthetic runs being green; bounded acceptance was not full acceptance.

## Confirmed failures / P0/P1/P2

- **P1 CI instrumentation coverage:** test_final_integration_workflow required a plugin not active in full CI. psycopg reached real DSN parser, Popen created an unintended harmless child on Windows (missing binary on Linux), global HTTP fixture returned a different denial. Fixed by explicit scoped real fixture in the security module, not global synthetic mode over real PG tests.
- **P1 conditional alias/process gaps:** old module-attribute patches left cached module/class connect, async connect, cached native sockets/DNS, arbitrary Python children and audit-level process calls uncovered.14 adversarial RED cases use invalid DSN, own loopback or direct audit emission only. No public request/actual DB was needed. New scoped class-function guards + CPython audit events + guarded reviewed-child bootstrap cover these tested paths;18 adversarial cases now pass. No fake constant PASS or weakened expectation.
- **P2 frozen source provenance:** shallow52/53 checkout lacks PR39 Git object. Exact source oracle now vendored with commit39, Git blob `a86da9cab8850e36b9e34333788197a2261d5ddf`, raw SHA256 `82771c658db45fcec88d1e50982e506dbf5e664b00c10cd3f86400a646130ea2`. Both verified before AST use, .gitattributes -text preserves bytes. No network fetch or ref fallback in test. Seven binding/corruption cases mandatory.
- **P2 Windows teardown consequence:** original unintended Popen child was not waited because test expected a pre-construction denial. Reproduced unraisable ResourceWarning; guard now denies before creation with safe construction state. Warnings are not suppressed. Asyncio self-pipe is a narrowly scoped stdlib socketpair exception; regular owned-loopback connect remains denied in security scope.
- **P2 stale mutation anchors:** host-arguments and contract-account operators became INAPPLICABLE after historical shared-config refactor. Retain historical anchors and bind exact current pair of config predicates as fallback. Operators are not dropped or relabelled without execution.43 applied operators, positive controls, baseline gaps0, survived0, inapplicable0. Counts: identity6killed/9schema-defended; security10/2; schema14/2. Defense is reported separately from kill.
- **P2 full-suite partition:** four explicit disposable PG cases are disabled outside their controller and would skip in ordinary full jobs. They remain mandatory4/4 in separate exact-source job; full jobs ignore only that module and gate all remaining identities. This is partition, not removal or synthetic replacement.

No new P0 found in bounded review. These are test/CI defects, not evidence that ADMINIT ownership/PPL/kernel identity has become VERIFIED.

## Reproduction / RED-GREEN

Read-only GitHub API verified five provided runs:40300412698/40300412621 at52 SHA;40301079889(PR)/40301073702/40301073716 at53 SHA. All completed FAILURE/attempt1. Branch audit/adminit-g0-windows-approval-20261026; event/head recorded, not misattributed to original52 branch. Private logs retained outside checkout.

Created two disposable shallow local source checkouts with exact52/53 and deliberately absent39 object. Four named failure identities + Windows teardown error reproduced on each, with harmless synthetic child exit only. Linux-specific missing executable variant observed in original hosted logs; no local Linux environment claimed. New targeted normal-conftest set179PASS after fixes. Original mandatory test functions retained. Additional child/socket/DNS audit and restoration checks use real guarded paths, not fake allow decisions.

Full local offline run:2479PASS/22SKIP/3deselected; no actual DB/DPAPI/native collector/installer. Local22=16DB unavailable+5symlink capability+1missing aiohttp; these cases are NOT_RUN/BLOCKED, not PASS. Three deselected:two live-DPAPI + installer. Explicit disposable4 partitioned to own hosted job. Final source-selected counts and exact SHA/JUnit evidence in dated receipt after freeze; preliminary selected1846PASS/2symlinkskips/2DPAPIdeselected before final policy6 cases. WindowsPowerShell5.1 byte matrix8/8 synthetic PASS; existing pure producer8/8 separate. Native/SCM/privacy337PASS/1capabilityskip; kernel947PASS/1capabilityskip/2DPAPIdeselected. These overlap and must not be summed as unique tests.

## Boundary scope and process lifetime

Full actual DB integration remains outside synthetic fixture. Identity-only pytest plugin records opaque exact collection without registering the synthetic autouse fixture. Scope exit restores original psycopg function code, Popen constructor and socketpair; restoration checked. Cached Python class/functions and native socket audit paths exercised while active. Unknown children deny by default; reviewed synthetic Python helpers run -I/-S/-B bootstrap with guards in child, no assumed inheritance. Known Git operations use verified PATH resolution, executable hooks/fsmonitor/global config/network protocols disabled; no old-object fetch. No arbitrary native child is implicitly allowed by its filename.

**Not an OS sandbox.** A malicious interpreter/native extension/ctypes/memory write or deliberate mutation of the guard can bypass Python instrumentation. Tests/child helper code and toolchain are reviewed/trusted; no assertion of hostile-code containment or arbitrary libpq C API interception. [Python audit-hook limitation](https://docs.python.org/3.12/library/sys.html#sys.addaudithook). Real OS sandboxing would require separate environment/policy authorization; no firewall/ACL changes made. Guards are function scoped, not a guarantee after leaked threads outlive teardown; lifecycle/drain tests remain mandatory.

## CI / exact evidence / failure privacy

New branch enables selected Windows/Linux + dependent real disposable18.1, full CI Windows/Linux/archive, Commissioning18.1 push, native-SCM offline, kernel offline/mutations and standalone privacy. No branch exclusion added for required full jobs, no old-SHA reruns. Exact checkout ref/head/tree receipts preserved. Full CI has identity-only source manifest + exact identity/status gate; selected gate remains complete1877cases. Frozen oracle independent of Git depth. All mandatory publication paths now require clean tracked source even on failure.

Four PG controller cases never count as full-suite skips; their separate hosted4/4 gate must pass. Full Linux allows only pre-existing Windows-installer skip; unexpected skips fail. CI Windows existing hosted-only native ABI probe and disposable Windows PG remain hosted activities, not ADMINIT. Linux Commissioning/controller version strict180001; Windows full-CI packaged binary remains independently pinned18.6 and is NOT claimed as ADMINIT18.1 runtime evidence.

Public projection strict schemas remove raw JUnit metadata/params/failures and prohibit raw process-probe/log/private payload. Genuine pre-fix Windows teardown produces duplicate testcase identity across phases: strict publisher may BLOCK that malformed report instead of dropping the error. Missing artifact is BLOCKED, never PASS. Normal sanitized failure evidence retains failures; tests verify rejection of forged counters/identities/dirty source. Mutations with INAPPLICABLE are rejected, not quietly published as green. Raw logs/XML stay private; public bundle uses opaque identities/fixed statuses. Upload provenance is not cryptographic proof of runner behavior; independent ZIP SHA256/manifest/source/event/run/attempt/job/OS verification is required once actual ZIP exists. Small host counters are not k-anonymous.

## HTTP.sys / encoding / physical readiness

54 strict HTTP parser and format-only observer,55 encoding matrix retained unchanged. Native producer uses verbose=yes while reported manual run was verbose=no. OutputEncoding ASCII is native stdin preference, not stdout corruption proof. Parent cp866 does not establish child setting; scripts set Console.OutputEncoding=UTF8. Correct Unicode/UTF8 JSON does not repair prior native decode mismatch and does not establish localized header semantics. Unknown/localized labels remain UNRESOLVED, no guessed translations/port/ping fallback. Source/lifetime and five service VERIFIED contracts unchanged.

Physical Windows/toolchain/loader/source/process/SCM/MetaScalp/HTTP ownership, PG5432 isolation, resources and filesystem remain NOT_RUN. Historical G0 refusals stay unresolved. Exact operator packet is [docs/ADMINIT_G0_FINAL_INTEGRATION_RU.md](docs/ADMINIT_G0_FINAL_INTEGRATION_RU.md). Primary path is ONE existing read-only R0-R5 invocation after source/hosted/operator preflight; format-only observer is an alternative separate decision, not an automatic second collection. No native collector/DPAPI/PG used locally here. No G1/deployment/merge/system/security/trading operations.


## Late independent PRs and final workflow correction

At final recheck new PR56/57/58 were discovered and read on exact heads:56 `0338c872eca2074df3ace22b32720520eee6c7f0`,57 `2fbfd17784b509d6858007f65cc196be4de176b2`,58 `cf8b92d721fb6cd53e5e1cf4be7cd69ac7df5219`.57/58 docs copied under reviews as historical, no inherited approval.58 deterministic fake attestation fault-injection tests were source-reviewed, run and included; no PG runtime code change.56 contains a new pure bool/readiness classifier plus tests despite its stale doc-only description; it is not connected to authenticated real receipts and was not imported as an authorization/evidence mechanism. Its full-E2E/OS-sandbox/Windows18.1 limits are retained as remaining blockers.

P2 workflow trigger/job-if mismatch was caught from actual first integration privacy run SKIPPED: trigger included new branch but job allowlist did not. RED1policy case reproduced, then allowlist fixed and6policy cases GREEN. Superseded integration SHA is not accepted. No skipped mandatory privacy job is treated as PASS. Final source exact counts/CI receipts supersede preliminary counts above.
