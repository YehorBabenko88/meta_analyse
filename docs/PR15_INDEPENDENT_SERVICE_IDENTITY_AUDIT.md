# Independent audit of PR #15: service implementation identity

Audited SHA: `69969c983335d784cff8930c7e95ec06d56de214`.
Comparison base: `3f4185fdb61ec1bab590203161cfc8face55335a`.
The original parallel/adminit-service-implementation-evidence branch contains only
that base; no competing implementation was created. This correction is stacked
on PR #15, targeting `codex/adminit-service-contracts`, without changing it.

Verdict: **NO-GO for host admission**. Two evaluator defects were reproduced and
corrected here. Protected-host feasibility, implementation provenance and
individual trust review remain gates. Static audit and synthetic tests do not
establish runtime identity on ADMINIT.

## Confirmed defects and minimal correction

### F1 — P1: empty SCM membership bypasses implementation requirements

Location at audited SHA: commissioning/process_identity.py:140-143 and generic
System32 fallback at the end of classify_missing.

Reproduction: construct an otherwise valid signed system-directory lsass.exe or
svchost.exe fixture, set both SCM complete flags true and both memberships empty,
and remove implementation/module evidence. The original evaluator returns
VERIFIED_SYSTEM_IMAGE / NATIVE_SIGNED_SYSTEM_IMAGE. Thus the stronger host
contracts are bypassed. This is an offline policy counterexample; it does not
claim the native collector routinely produces this input on a running host.

Correction: include hosts from WINDOWS_SERVICE_CONTRACTS in the existing
known-service-image guard. Empty membership now returns SERVICE_IDENTITY_UNAVAILABLE.
All five contract fixtures exercise this guard. Other signed System32 images
retain their existing behavior; the generic synthetic fixture now uses winlogon.exe.

Owner: process-identity policy maintainer. Acceptance: all five empty-membership
cases reject without implementation evidence, while complete named-contract
fixtures still verify. Confidence: high, executable reproduction.

### F2 — P2: duplicate membership is accepted as complete evidence

Location at audited SHA: commissioning/process_identity.py:139-153.

Reproduction: duplicate the same DoSvc row in both snapshots. The original
evaluator returns VERIFIED_SERVICE. It never checks uniqueness of SCM names.
One-sided duplicates already reject as a membership change; the defect is the
identical malformed lists accepted at both endpoints. Native registry enumeration
normally yields unique names, so this is evidence-validation hardening rather
than a demonstrated native collection exploit.

Correction: reject missing/empty/non-string names and case-insensitive duplicate
names before comparing membership. Tests cover duplicates in either endpoint
and both endpoints. Mixed trusted/unreviewed membership is checked in both orders.

Owner: process-identity policy maintainer. Acceptance: duplicate membership cannot
produce verification. Confidence: high, executable reproduction.

## Independent boundary review

- **PSAPI / VM_READ / PPL:** ReadModules opens 0x410, correctly requesting
  PROCESS_QUERY_INFORMATION | PROCESS_VM_READ. It does not enable privileges or
  use a fallback to bypass protection. Open/enumeration/path/count/list-change
  errors leave complete false; the evaluator requires complete=true and error=0.
  GetModuleFileNameEx with a real module handle needs these rights; the limited
  query exception for a NULL module does not help DLL inspection. Protected LSA
  can prevent this access. Hosted self-enumeration is not evidence that LSASS
  module enumeration is available on ADMINIT. No such access was attempted here.
- **PID reuse:** native before/after creation times match exactly; CIM has the
  documented microsecond tolerance. Both module snapshots require the exact
  native PID and FILETIME creation value, so a reused PID with another creation
  time rejects. Each module enumeration uses one process handle. The native
  final liveness check bounds later collection. Endpoint equality cannot exclude
  transient ABA changes or a manipulated loader list.
- **SCM -> host -> DLL:** every attached service is evaluated. Native SCM supplies
  PID/state/binary path/type/account; independent registry values supply matching
  host configuration and reviewed DLL source/path, including explicit absence
  for integrated SamSs. Two complete module sets must agree and contain host and
  expected DLL. Host and DLL signatures/hashes are checked separately. Unknown
  members block the entire process. This is stricter than trusting a host name
  or Microsoft publisher, but module presence alone is not service dispatch proof.
- **Shared-host isolation:** mixed unknown members reject in both orders. The
  three-service fixture requires all three implementation proofs. The policy
  does not verify every additional loaded DLL or prove which service invoked a
  particular DLL/export; VERIFIED_SERVICE must not be interpreted as a clean
  memory attestation for the whole process.
- **Configuration scope:** registry snapshots retain raw/expanded paths, account,
  type and selected DLL source. They do not retain all registry value kinds,
  ServiceMain/export selection or svchost group registration. DLL expansion uses
  the collector environment. Therefore claims that *all* configuration changes
  are detected are unsupported; the documented subset is what is compared.
- **File/hash/signature/reparse:** the helper checks ancestry once, then two disk
  hashes around Authenticode. It has no final-handle/file-ID link between mapped
  module and checked disk file, no separate final signer/reparse snapshot, and
  no approved hash pin set. Stable hashes here mean sampling stability, not an
  individually approved version or full-interval immutability. These are residual
  provenance limits, not a demonstrated ADMINIT substitution in this audit.
- **Privacy:** public_report projects counts/reason codes, not raw process proof;
  collect_facts moves the new nested proof into private_inventory. Raw private
  records remain within the existing DPAPI path. The artifact guard recognizes
  new wrapper keys but is explicitly heuristic: a detached paths/DLL/subject
  fragment is not universally detected. Existing privacy tests pass; no private
  SCM records or DPAPI observation were opened or published for this audit.

## Validation

Red run on uncorrected production code with added regressions: **8 failed,
42 passed**. Five failures demonstrate F1; the both-endpoint duplicate demonstrates
F2; the other two assert the new deterministic malformed-membership refusal.

After correction:

- Focused identity/diagnostic/authorization suite: **179 passed**.
- Full local suite with all DSN environment variables removed and Qt offscreen:
  **828 passed, 16 skipped**, 65.04 seconds. Skips: 3 lifecycle PostgreSQL cases,
  11 storage-ingestion PostgreSQL cases, 2 Windows PostgreSQL smoke cases.
- git diff --check: clean. No live collector, diagnose, deployment, smoke30,
  service/registry/ACL/Norton changes or PostgreSQL connection was executed.

Existing GitHub Actions on the exact audited SHA were independently read:
[CI pull-request run](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39594566344)
completed successfully: diagnostic **169 passed** on Windows and Linux; full
Windows **834 passed**, Linux **833 passed, 1 skipped**.
[Storage integration run](https://github.com/YehorBabenko88/meta_analyse/actions/runs/39594566307)
also completed successfully. Those results belong to PR #15, not this correction.
They did not cover the new counterexamples.

This correction is published with [skip ci] to avoid automatically executing
existing native collection and database-provisioning jobs under this task's
restrictions. No new Actions result is claimed. Required checks may remain pending;
the correction remains a Draft PR. A separately authorized synthetic-only CI run
or disposable-runner verification is still required before integration.

## Remaining blockers and owners

1. Security/policy reviewer: explicit individual approval for each of KeyIso,
   SamSs, VaultSvc, DoSvc and wscsvc. Existing fixed descriptors and successful
   synthetic fixtures do not substitute for that review.
2. Evidence-provider maintainer: independently reviewed service implementation
   attribution, mapped-file identity/provenance and exact configuration scope.
   If the stronger full-interval requirements apply, extend evidence accordingly;
   do not label current path/hash samples as satisfying them.
3. Windows/platform owner: establish whether protected-host evidence is available
   through an approved provider. AccessDenied remains UNRESOLVED. No weakening of
   PPL, ACLs or endpoint protection is an acceptable acceptance criterion.
4. CI maintainer: verify the correction on its exact SHA with an authorized
   synthetic-only job; distinguish this from existing PR #15 CI and from all
   unrun physical admission/stability gates.

No merge or deployment recommendation follows from this report.

## Primary references

- [GetModuleFileNameExW rights and mutable-list limits](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getmodulefilenameexw)
- [EnumProcessModulesEx snapshot limits and WOW64 behavior](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-enumprocessmodulesex)
- [Added LSA protection](https://learn.microsoft.com/en-us/windows-server/security/credentials-protection-and-management/configuring-additional-lsa-protection)
