# PR27 content boundary review

Frozen source PR27: `2ecb671aa298c1e47ce304ab48f41ef85cd242a8`, tree `47be845b4a4ca815c90104777b227eb70aecd96c`. This isolated follow-up does not change PR24–27.

Six new synthetic assertions were red on frozen PR27, then green with this fix:

- The default ElementTree parser discards XML comments and processing instructions, accepts DTDs and expands internal entities. Post-parse structure checks therefore accept unprojected input carrying hidden raw metadata. No external-file/network exploit is claimed; all witnesses use tiny synthetic strings.
- `str(exc)` on malformed numeric counters and OSError leaks raw values/paths into CLI stderr. Witnesses contain only synthetic sentinels.

The parser target now rejects comments, PI and DTD at parsing time, before entity handling. Reads are bounded on actual file descriptors (8 KiB JSON, 8 MiB XML), rather than relying on earlier stat sizes. Test counters must equal canonical actual counts. CLI refusal emits a fixed safe code without exception messages. Success JSON is unchanged. Positive compatibility is tested against real, authenticated PR26 artifacts as well as fixtures.

No new dependency or privilege is required. This is not a claim of universal XML safety independent of parser/profile. No external entities, host collection, physical machine changes or database operations are used by tests.

The identity gate still verifies shape, uniqueness, minimum count and equality across four cells. It does not derive an authoritative expected identity manifest from the expected commit; uniformly forged names across all four cells are a documented custody limitation, not a new semantic guarantee. Real acceptance must independently compare all identities to exact-source pytest collection and verify GitHub run/job/attempt/artifact provenance. It also cannot prove OS identity from files alone: platform custody belongs to authenticated artifact receipts. Parent-directory reparse/TOCTOU protection is not a directory-capability security boundary; inputs must remain in a reviewer-owned stable extraction tree.

Local original suite: 11 pass, one Windows symlink privilege skip (BLOCKED). With added security suite: 29 pass, three symlink skips on this restricted workstation. Hosted original PR27 full CI JUnit independently shows all original 12 cases executed/passed on Windows/Linux; full Linux has a separate unrelated Windows-only installer skip. Do not convert skips into PASS. New synthetic-only workflow runs both suites on Windows/Linux at the follow-up SHA; exact results belong to its run artifacts, not this static document.

Authenticated real PR26 artifacts: push 39925828647, PR 39925836041, attempts1; four datasets, 83 identities each; expected SHA `8885381efa5c65741ae765f55bc230baccbc0ccc`, tree `a28f5e17c94ddc7d1ad8bfb3e73e7f6423ecf3c7`. ZIP digests were matched to GitHub metadata before extraction. Original content gate returns CONTENT_PASS_ONLY. Exact identity-set comparison is independent of that gate.

Existing PR27 full CI runs 39928368057/39928375391 and PostgreSQL18 run39928368055 were read-only evidence sources, not dispatched or rerun. Source receipts and archive/file SHA256 checked. Their raw JUnit contains runner hostname metadata; the inherited broad privacy gate is not a strict JUnit projection. Raw host-bearing reports/logs are not republished. The archive-only artifact lacks its own source receipt; run/SHA/ZIP custody is available, standalone source receipt is BLOCKED. These legacy publication issues are outside the minimal content-parser fix and remain open.

Full/native/PG jobs are excluded on this follow-up maintenance branch. The new workflow installs pytest only, uses --noconftest and temporary synthetic files, then projects JUnit and checks privacy before upload. No existing trigger lists are broadened. No merge/deployment. ADMINIT NO-GO.
