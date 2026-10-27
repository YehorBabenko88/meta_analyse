# PR60 read-only access and provenance control

Production stays PR60 0cc8c44/a85846d. New stacked control branch starts at
PR64 d45d9a0. No src/commissioning changes, no physical execution.

1. RED tests: strict manifest, real-byte mismatch, incomplete roles, symlink,
   public privacy, type errors, access snapshots, current-token scope and refusal.
2. Implement stdlib-only offline verifier plus explicitly invoked Windows reader.
   AccessCheck uses real duplicated current process token; impersonation refuses.
   No arbitrary SID contexts, privilege changes, writes, Add-Type or subprocess.
3. Correct parent runbook: CreateDirectories alone is not DeleteChild; .NET
   directory creation is not exclusive. Keep malicious precreation BLOCKED.
4. Synthetic-only Windows/Linux workflow, exact source and existing public JUnit
   projection. No hosted native calls. Run local checks, review, new Draft PR.
5. Document bootstrap independent manifest approval and loaded dependency scope;
   file matches do not independently authenticate the approver or loader chain.
   Other subjects, policies, races and physical admission remain BLOCKED.
