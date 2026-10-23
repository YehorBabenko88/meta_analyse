# Legacy JUnit public artifact privacy — isolated follow-up

Based on PR28 exact HEAD `15a9d25233cc2383f2f771c0536bb1b1eeaae20a`. This Draft is a conservative offline refusal gate. It is **not** a repair to pre-existing published GitHub artifacts, not a JUnit projection, and not an authorization for native/physical runs.

Independent PR27 acceptance found runner `hostname` metadata in full Windows/Linux/PostgreSQL/archive JUnit uploads despite the broad privacy scanner passing. The new script rejects unapproved attributes, embedded output, failure messages, unexpected tags, parser constructs, duplicate testcase identities and malformed XML; tests use synthetic values only. Do not upload raw JUnit, pytest log, PostgreSQL logs or host inventories just because a generic secret scan passes.

Gate integration into all existing workflows is intentionally **not** claimed here. Existing full CI/PG workflows still publish raw reports; before replacing their publication path, independently review the scope, ensure that collection failures remain visible privately, and preserve FAIL/BLOCKED instead of silently projecting an erroneous PASS.

This branch does not change production, native/PG workflows, public artifacts or source PRs #24-#28. Full privacy rollout and JUnit provenance remain BLOCKED until a separate scoped workflow review. ADMINIT NO-GO.
