# HTTP.sys refusal: design and implementation plan

Exact base PR52 8a1c20184cbd878097f62530fc07630568fb7f84. User authorizes separate branch/Draft PR for confirmed defects and aggregate-only diagnostics, no physical execution.

1. Capture RED parser cases (duplicate/contradictory/spoofed count, ignored HTTPS, invalid PID, URL trailing garbage). Tighten only; preserve existing English verbose positives and no ownership fallback. Unknown locales/summary remain refused.
2. New separate format-only diagnostic: standard-policy system PowerShell child invokes system netsh once with the SAME view=requestq verbose=yes as producer. Raw text stays in parent memory. No Add-Type/CIM/PG/DPAPI/MetaScalp/HTTP ping. Source binding before/finally; lifetime NOT_EVALUATED. Always FAIL_CLOSED/NONE/exit1. Public projection contains only fixed enums, coarsened counts/structural booleans, no per-line structures, raw strings, hashes, labels, PID/URL/process/path.
3. Pure projection/CLI fake tests including unknown locale, malformed JSON/types, source drift, child error, privacy sentinels and collision. No real netsh invoked. Add selected suite/branch-only CI and preserve existing source/privacy gates.
4. Exact SHA/tree/merge-base/RED/GREEN/JUnit/hosted evidence; one new read-only format procedure AFTER review, not automatic; unresolved G0/G1 remain NO-GO.

Rejected: guessed translations/locale forcing, broad parser fallbacks, ownership from port/ping, PID4/name exceptions. Real ADMINIT format and localized vocabulary remain unknown until approved diagnostic; format projection alone may be insufficient to implement a trusted localized parser.
