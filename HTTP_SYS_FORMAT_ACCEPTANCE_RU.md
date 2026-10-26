# HTTP.sys: bounded parsing and format-only diagnostics

## Scope / current evidence

Base PR52 HEAD8a1c20184cbd878097f62530fc07630568fb7f84. User ADMINIT observations are accepted as reported, not independently collected here. Original host-facts producer uses **view=requestq verbose=yes**; the manual observation used **verbose=no**. These are different detail modes. Microsoft documents modes, not a stable English/localized textual schema: [netsh http](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/netsh-http), [show servicestate](https://learn.microsoft.com/en-us/windows/win32/http/show-servicestate).

The old parser supports a narrow English verbose-like profile: column-zero Request queue name delimiter, exactly one Number of active processes attached:1, one indented ID:<decimal>, image: line and HTTP loopback registered URL evidence. Summary numeric Process IDs and unknown locales are unsupported. Existing minimal tests are synthetic profiles, not captured Windows output. No guessed Russian headers are introduced; Cyrillic alone does not establish output locale or correct decoding. Actual ADMINIT header vocabulary/layout remains unknown from the supplied counts. Listener PID different from application PID and successful /ping establish neither ownership nor a defect by themselves.

## Confirmed bounded defects / RED-GREEN

P1 conditional evidence-admission defects in the pure HTTP ownership parser: first duplicate count wins, unanchored spoofed count label, ignored HTTPS registrations, zero/out-of-range PID and URL trailing garbage. Eight synthetic inputs were accepted on52 that must refuse; targeted RED8FAIL/11PASS. Tightening rejects them without accepting a new format. All33 targeted parser/old commissioning cases then pass. This does not prove a practical Windows-generated exploit or explain the physical localization refusal.

No process VERIFIED predicate, protected-process exception, service contract or source/lifetime check is relaxed. Source/lifetime diagnostics adapter and native collector unchanged. Unknown/localized/summary/multiple queues/multiple processes/wildcard output remain refused. Old English positive fixture stays positive. No TCP/ping fallback.

## Separate diagnostic

`commissioning/http_sys_format.py` is the sole public entry point. One policy-respecting system WindowsPowerShell child runs new **internal/private** `http-sys-format.ps1`, which runs system netsh once with the same view=requestq verbose=yes. No Add-Type, process/native C# collection, CIM, PG, DPAPI, HTTP ping or MetaScalp actions. Raw stdout/stderr is captured privately/in-memory and never persisted by this tool. No standalone internal .ps1 invocation/transcript/redirection.

Before/finally source_binding is reused; lifetime is explicitly NOT_EVALUATED_DIAGNOSTIC_ONLY. Output always FAIL_CLOSED/NONE/exit1. Format AVAILABLE means only that structural projection was computed. Ownership NOT_EVALUATED, format_support NOT_ATTESTED always. No new VERIFIED path. This snapshot must not be combined with another PID observation as ownership proof.

Public fields: fixed enums, count buckets, ASCII English marker occurrence/indentation families, nonASCII/Cyrillic/replacement/control booleans and fixed target-token presence. No raw/hashed labels, line samples, per-line arrays, PID/count values copied from input, URLs/paths/process names/hostname/SID/DSN/raw errors. Target-token may occur outside a URL; it is explicitly not proof of a listener or owner. Bucketed/rare structural features are not k-anonymity; local-only default.

Strict JSON/type/size/exit-code checks reject malformed child output. No English/Russian localization guesses. If markers remain absent the real textual format is still unknown: do not reverse-map bucket counts into translations. A later documented-API or locally source-reviewed format project would need separate evidence.

## Tests and limits

58 new cases: parser ambiguity/malformed/localized refusals and unchanged positives; projector strict types/bounds/privacy sentinels/100 property examples; CLI fake child/token/source drift/collision errors; duplicate-key/NaN/wrong-type child JSON; fixed child command/policy. Full suite pre-freeze1800PASS/2allowed symlink skips/2live-DPAPI deselected; final exact SHA/JUnit/CI evidence recorded separately after freeze. PS script syntax parsed; actual system netsh never invoked. Producer locale/native encoding not physically attested; replacement-character flag is only a diagnostic clue, not encoding correction. No crash durability or malicious-local-admin namespace resistance claimed. New diagnostic's output follows existing exclusive-create convention, not crash-atomic publication.

## One physical read-only procedure — DO NOT RUN AUTOMATICALLY

1. After source review verify NEW Draft PR SHA/tree, Windows/Linux hosted identities/privacy; complete existing operator preflight for trusted Git/base Python3.12x64/WindowsPowerShell5.1x64/System32 netsh and effective persisted/GroupPolicy. Validate every new .py/.ps1 too. Do not reuse old52 hashes for new candidate. No policy changes, auto-elevation, loader overrides, source signing/Unblock-File, reparse/alias output or concurrent writers.
2. Approved absolute interpreter/source root, clean exact checkout, no ignored pyc/shadow modules/site hooks, new local output outside source/venv/private authorization. Keep PG* env untouched; no SQL. If any prerequisite unknown, STOP.
3. Operator explicitly approves exactly ONE format-only collection. Prepared command (replace exact SHA/tree only from final receipt):

```powershell
& $g0Python -B -E -s -S (Join-Path $g0Repo 'commissioning/http_sys_format.py') --expected-sha <NEW_EXACT_SHA> --expected-tree <NEW_EXACT_TREE> --output <NEW_APPROVED_LOCAL_JSON>
$g0Exit = $LASTEXITCODE
# STOP; exit1 is expected. No retry and no full R0/native collection automatically.
```

4. Compare stdout/new file/current source binding; expect schema1, HTTP_SYS_FORMAT_ONLY, FAIL_CLOSED/NONE/exit1. AVAILABLE only for complete structural projection, lifetime NOT_EVALUATED. On UNAVAILABLE/partial/mismatch/source drift, preserve locally and STOP. No raw error dumps/transcripts. If optional sharing is authorized, share only the complete reviewed aggregate JSON after privacy review; never internal .ps1 stream or user paths.
5. This format-only command does not call existing Add-Type native collector. Full R0-R5 would be a separate decision/run and is **not** authorized automatically by a successful format projection. No refresh of physical process/SCM/Metasc identity has occurred here. G0 remains FAIL_CLOSED, authorization NONE, G1 NO-GO. No changes to Windows/HTTP.sys/Norton/Defender/ACL/services/registry/PG/MetaScalp, no merge/deployment/trading.
