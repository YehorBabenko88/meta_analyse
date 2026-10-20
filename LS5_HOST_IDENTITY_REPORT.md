# LS5 host identity and conflict report — 2026-10-20

**Verdict: NO-GO for starting a 30-minute test on this LS5.** No enrollment authorization or smoke run was created. No service/task/configuration was stopped or changed.

Expected hostname and Windows account match fresh OS-derived values (not COMPUTERNAME/USERNAME environment). Windows11 Pro/build26300 confirmed. Installation MachineGuid, Windows installation date, hardware UUID and current-user SID are present and were used privately; their raw values and nonce are not published.

Safe HMAC-SHA256 fingerprint: `9bb114ecf560f8251502aeec78a0cf870d481dda7c98624989ad98a101533ffc`. Its random nonce stays in a DPAPI CurrentUser observation outside Git. Same-user DPAPI decrypt/roundtrip and ciphertext-tamper rejection were tested. A real different-machine/user decryption attempt was not performed; mismatch tests are synthetic. Full clones of all OS/hardware identities and malicious local administrators are outside this local safety boundary.

## Grid and conflict evidence

Independent read-only inventory observed289 visible services,205 scheduled tasks and344 processes at that snapshot. No Grid service/task/runtime was positively identified. Microsoft task-name false positives were excluded. This is not proof of absence:150 process executable paths were unavailable, and a commissioning directory denied deeper enumeration.

Deployment footprints exist under `%ProgramFiles%/BybitClusterGrid`, `%ProgramData%/BybitClusterGrid`, `%ProgramData%/BybitGridCommissioning`, and `%USERPROFILE%/GridCommissioning`. Visible metadata includes release/current-version, runtime/spool/deploy and configuration-file names. Secrets and .env contents were not read by this inventory. Installer remnants versus active/production Grid cannot be certified from these observations. Operator's statement that Grid is not deployed is retained as an assertion, not technical clearance.

New collector independently reports4 Grid-directory findings and1 inventory coverage error. No exchange-credential or production-DSN variable was found in inspected Process/User/Machine scopes. Values are not published; detection covers recognized credential names plus PostgreSQL DSN shapes, not arbitrary unknown secret formats. No Grid TCP listener could be conclusively attributed; unavailable process paths prevent an absolute all-clear.

## MetaScalp and PostgreSQL

Two executable candidates found, both file-version0.0.9.0 with Valid Authenticode; uninstall registration reports1.0.291 (different metadata source, not assumed equivalent). No MetaScalp process/API listener observed on17845–17855; no local API GET was attempted. The operator must select and approve the trusted signed executable SHA and start/configure its API manually; nothing was installed or launched.

Existing PostgreSQL18.6 is ready on55432 and listens on all IPv4/IPv6 interfaces. Authentication and role isolation remain unverified. See LS5_POSTGRES_PREFLIGHT.md. No existing-cluster SQL or grants were changed.

## New authorization boundary

Candidate5928b4e3aadac55d64bdd013c83ed698cfd8d838 replaces the name-only ban with explicit LS5/account-specific DPAPI enrollment, fresh installation/hardware/SID fingerprint, operator no-Grid attestation, expiry and exact candidate/manifest digest. It also binds a private loopback cluster/database/role and approved signed MetaScalp software/API port. LS7/other accounts cannot enroll via this procedure. There is no ignore-host flag.

Fresh Grid findings, incomplete coverage, wrong identity/source, production DSN/credentials, broad DB privileges, missing API or TLS failure reject launch. Existing PASS JSON is never trusted: launch repeats preflight. Only smoke30 admission is supported;30min requests normal close and drains pending writes, not forced exit.

**Unresolved:** classify Grid footprint and complete coverage under the same approved user; establish isolated PostgreSQL grants; select/start/verify signed MetaScalp API; operator explicitly authorizes only after technical clearance. Until then NO-GO, including if CI is green. Raw inventory and DPAPI observation remain private outside repository/package.
