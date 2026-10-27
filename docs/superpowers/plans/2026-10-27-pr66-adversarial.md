# PR66 adversarial remediation

Exact base419d336480d9ec3b40a8bc96a402874f434cc3c5, production PR60 immutable.
1. Independently reproduce late thread impersonation, cleanup return failures,
   ABI layout corruption, malformed AccessCheck status/mask/token replies.
2. Fail closed on final thread context and cleanup errors, attempt every acquired
   resource exactly once, fixed-width ABI with size/offset checks before DLL load.
3. Rename caller-pin byte match to avoid approved-authority implication. Bind
   authority packet bytes to separately approved pin, but do not claim signature
   verification or supply an invented approved baseline.
4. Add explicit operator packet and no-logon other-subject review protocol.
5. Update scoped synthetic workflow branch filters/case gate, RED/GREEN and
   privacy regressions, independent review, new stacked Draft PR and hosted ZIPs.
No physical/native invocation or source branch modification.
