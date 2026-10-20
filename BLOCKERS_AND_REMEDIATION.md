## LS5 adaptation update — 2026-10-20

Tested source: `5928b4e3aadac55d64bdd013c83ed698cfd8d838`. Draft PR #12. **Actual LS5: NO-GO for 30min; NO-GO for 2h and 24h. All timed trials NOT RUN.** The earlier conditional admission applied to a cleared isolated host and does not authorize this LS5.

[Exact-source Windows/Linux CI](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39480839261): Windows698 passed, zero skips; Linux697 passed, one expected Windows installer skip. [Additional PG18 CI](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39480839300):697 passed, same expected skip. Every job recorded10 fresh-process lifecycle batches of67 passes. Local focused host/commissioning regressions:65 passed. Raw JUnit/source provenance and safe host counts: `docs/ls5_commissioning_evidence/`. These are new reproducible results, not validation of historical586/670 claims.

Host authorization now requires DPAPI-bound multi-identifier HMAC identity, explicit operator approval, complete fresh Grid/environment checks, exact source and manifest digest, isolated PG18 listener/data directory and minimal role, approved signed MetaScalp API owner, mandatory TLS verification. No bypass flag. See `LS5_HOST_IDENTITY_REPORT.md`, `LS5_POSTGRES_PREFLIGHT.md` and `WINDOWS_COMMISSIONING_PLAN.md` for evidence and operator commands.

Current blockers: Grid deployment directories and incomplete process-path coverage; existing PostgreSQL18.6 listens on55432 wildcard addresses with role/isolation unverified; signed MetaScalp files exist but no active API. No enrollment authorization, separate cluster/role, application run, service stop or existing database changes were made.

Residual limitations: bounded scans cannot prove absence of renamed custom agents; real cross-machine DPAPI test not performed; fresh OS scans before terminal requests may add latency (up to collector timeout), not covered by synthetic UI benchmark;30min timer requests normal shutdown rather than imposing a hard exit. Never claim duration/reconciliation success without real host logs.

---

## Historical commissioning record (superseded for LS5 admission)

# Blockers/remediation â€” 2026-10-20 re-audit

Candidate **446c72bd97cacc31f9937c9ab941d11539733be4**. Conditional admission to supervised30-minute smoke only after approved target preflight. Actual activation remains NO-GO until prerequisites pass;2h/24h remain NO-GO.

| Blocker | Evidence/remediation | Scoped code verdict | Target condition |
|---|---|---|---|
| Orderbook autonomous recovery | Invalid/sequence regression/silent/busy feed tests; real sockets close; fresh epoch/snapshot; immutable observations; bounded interruptible backoff | GO | Real target outage/recovery and fail-closed state |
| REST/TLS | Real untrusted/wrong-host rejection; valid localhost; timeout/cancel/abort cleanup; verified public app GET200/TLS1.3 | CONDITIONAL GO | Target app preflight; historical failure remains unexplained |
| Archive/PostgreSQL | Bounded Decimal;11mandatory cases Windows/LinuxPG18.6; actual server lock wait and timeout/no mutation; atomic checkpoint/resume | GO | Target archive load/cancellation/reconciliation |
| Shutdown | Schema/collector writes drained;5mandatory shutdown cases;10x67per environment; partial HTTP/real WebSocket closure | CONDITIONAL GO | Target close during startup/load/write; no early acknowledgment |
| CI/SHA enforcement | Exact11PG+5shutdown identities, required skips rejected, independent Windows gate, source/version artifacts | GO for446c72b | Reject d3856c7 and unreviewed branch mixtures |
| Target/long-run evidence | Hardware preflight/timed logs absent; queue/drop reconciliation unknown | NO-GO for2h/24h | Reviewed30m then2h evidence, measured missing metrics, subsequent approvals |

Rejected d3856c7 had green Windows Actions but639 passed/11 skipped because TEST_DSN and gate were lost during independent integration. Final446c72b has651 passed/0 skipped. Published PR9 gate also accepts unrelated cases because escaped newlines swallow enforcement; final candidate deliberately replaces it.

Immediate stop: wrong source/host/DB, TLS failure, write/order/level attempt, stale/gapped data treated verified, unsafe recovery, corruption/checkpoint mismatch, leaked resources/early stop acknowledgment, unresponsive/unbounded runtime or missing logs. Request safe disconnect/close; never force-kill pending writes to manufacture a PASS. See WINDOWS_COMMISSIONING_PLAN.md.
