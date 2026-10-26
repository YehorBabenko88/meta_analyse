# HTTP.sys encoding boundary acceptance — Windows PowerShell5.1

Base: PR54 HEAD0883a979ba364a778a3ca78d0dc4fdc5026e46d7 (itself based on52). Separate tests/docs branch. No production `commissioning/` or `src/` changes.

## Facts vs unknown

User-reported physical ADMINIT outer shell: Console.OutputEncoding cp866, OutputEncoding us-ascii, Culture/UICulture ru-RU. No new physical netsh/host collection occurred here. These values do not prove stdout corruption or identify the actual HTTP.sys header vocabulary.

Both host-facts.ps1 and http-sys-format.ps1 explicitly set Console.OutputEncoding=UTF8NoBOM **inside the child before native capture**. The outer interactive cp866 observation therefore does not establish child decoder state. `host_identity.collect_facts()` and format diagnostic capture bytes and decode outer JSON using strict utf-8-sig; no cp866 fallback/errors=replace is used at that boundary.

## Four distinct boundaries

1. **PowerShell -> native stdin.** OutputEncoding governs encoding of text piped INTO a native program. Current `netsh ...` invocation passes arguments and no text stdin pipeline. ASCII here is not evidence that native stdout is corrupted. [Microsoft PowerShell5.1 preference documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_preference_variables?view=powershell-5.1#outputencoding) and [PowerShell Team explanation](https://devblogs.microsoft.com/powershell/outputencoding-to-the-rescue/).
2. **Native bytes -> PowerShell strings.** Native writer chooses bytes. WindowsPowerShell native capture uses its decoder; real Desktop5.1 synthetic test verifies Console.OutputEncoding selection with forced cp866/UTF8 emitters. The console setting can also influence a console-aware native writer, so a forced synthetic cp866 emitter does NOT prove real netsh continues to emit cp866 after setting65001. Whether actual netsh respects output code page/uses another encoding is still unknown. PowerShell6 source has analogous Console.OutputEncoding selection, but it is not used as proof of5.1: [v6 source](https://github.com/PowerShell/PowerShell/blob/v6.0.0/src/System.Management.Automation/engine/NativeCommandProcessor.cs).
3. **PowerShell Unicode -> JSON/stdout bytes.** Cmdlet/ConvertTo-Json values are .NET Unicode. Direct stdout under script UTF8 setting is different from WindowsPowerShell Out-File/`>` file defaults. No raw `>`/Out-File transport is used. UTF8 serialization preserves the string PowerShell already has, including mojibake/replacement if stage2 went wrong. [Microsoft character encoding](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding?view=powershell-5.1).
4. **JSON bytes -> Python.** Strict utf-8-sig accepts UTF8 with/without BOM; invalid/truncated UTF8 or cp866 wire with literal Cyrillic raises. JSON duplicate keys/NaN/Infinity remain rejected by strict_loads. ASCII-only JSON is byte-compatible across these encodings; no encoding detector/provenance is inferred from that.

## Observed synthetic Desktop5.1 matrix

`check_http_sys_encoding_contract.py` runs8 independent hidden PowerShell5.1 children, ru-RU thread Culture/UICulture only inside each. Each invokes only a synthetic Python byte emitter. CREATE_NO_WINDOW avoids sharing the interactive console; no chcp/global encoding/profile/registry updates. Inherited process ExecutionPolicy override is removed in child env, system module path chosen, no ExecutionPolicy switch/Bypass. -File respects persisted policy; refusal means BLOCKED, no inline fallback. Native stdout/stderr stays captured, only a fixed PASS/BLOCKED line is printed. No netsh/Add-Type/CIM/native collector/DPAPI/PG/MetaScalp probe.

| Emitted bytes | PS native decoder | OutputEncoding choices tested | Result after UTF8 JSON/Python |
|---|---|---|---|
| cp866 | cp866 | ASCII and UTF8 | Exact Cyrillic preserved |
| UTF8 | UTF8 | ASCII and UTF8 | Exact Cyrillic preserved |
| cp866 | UTF8 | ASCII and UTF8 | Wrong text with U+FFFD; valid outer JSON does not repair |
| UTF8 | cp866 | ASCII and UTF8 | Mojibake, potentially no U+FFFD; valid outer JSON does not repair |

All8 actual synthetic engine cases PASS locally. They model possible emitter behavior, not netsh output. Lack of U+FFFD is not proof of preservation; Cyrillic presence is not proof of correct decoding. No claim of real ADMINIT toolchain/HTTP.sys acceptance.

## Localization and fail-closed

Culture/UICulture may influence resources, but ru-RU alone does not establish exact netsh messages/fallback language. Correctly decoded unknown/localized labels remain unsupported by the narrow English verbose-like parser. No Russian headers guessed, no locale forcing for production, no ownership from port/ping. Summary verbose=no also differs from producer verbose=yes independently of encoding.

cp866 and UTF8 are ASCII-compatible: a mismatch alone does not erase original literal ASCII English labels. Missing English markers therefore cannot be attributed to OutputEncoding=ASCII or these two codecs alone without more evidence about bytes/format. UTF16/BOM/other formatting are separate possibilities, not established facts.

21 new Python synthetic tests cover two-stage codec model, both BOM modes, strict malformed UTF8/cp866 outer refusal, duplicate/NaN/Infinity JSON, unknown-header Unicode roundtrip and ambiguous queues. All21 PASS. Previous58 parser/format cases remain included. Full pre-freeze1821PASS/2allowedsymlinkskips/2liveDPAPIdeselected; final exact-candidate identities and CI in external receipt. Windows actual8-case checker added as separate normal CI step; Qt and all existing synthetic tests retained. Source collector, native/SCM/service VERIFIED and source/lifetime contracts unchanged.

## Reproduce only synthetic

```text
python -B scripts/check_http_sys_encoding_contract.py --shell powershell.exe
```

Use existing approved interpreter/shell; no policy changes. The checker creates/removes only synthetic temp files and hidden children. It refuses non-Windows/non-Desktop5.1 or blocked policy rather than changing the system. Linux runs Python codec/unknown/ambiguity models; Desktop5.1 engine result is separately Windows-only, not claimed as Linux execution.

## Physical next step / limits

No physical run is performed or automatically requested by this investigation. Existing54 format-only procedure can be considered only after its own source/hosted review and operator preflight; it reports decoded structural flags, NOT actual byte encoding or localized header semantics. No production change is justified merely by outer shell settings. If further evidence is needed, a separately reviewed aggregate-only byte-boundary observer could compare validity/roundtrip flags without raw labels/bytes/hashes; not implemented or authorized for execution here. Do not retry live netsh, force culture, change global Console/OutputEncoding, use Bypass, or accept a localized layout by guesswork. G0 FAIL_CLOSED/NONE, G1 NO-GO.
