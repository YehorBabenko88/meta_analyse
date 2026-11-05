# Private headless historical-analysis API

This adapter makes the existing `grid_history_adapter.analyze_grid_history`
function available to an owned Unified process profile. It introduces no
controller, scheduler, task deduplication authority, persistent data store, GUI,
exchange connection or order/training operation. Grid remains the fleet/task
authority. This is functional offline historical analysis, not a complete live
feed, paper-session service, Windows service qualification or physical readiness.

Running `python -B -m meta_analyse.headless_service` defaults to PREPARE_ONLY:
JSON stdout, no listener and no output files. Existing desktop entry points,
application code, dependency locks and CI workflows are unchanged.

## Owned execution profile

Only an independently admitted owner profile may execute this service. Plain
`python -B -m ... --execute` is refused: `-B` prevents cache writes but still
permits reading poisoned bytecode. Use Unified's single externally pinned
raw-script bootstrap, not a new Meta launcher:

```text
python -I -S -B /pinned/Unified/unified_system/owned_python.py
  --source-root /canonical/Meta --module meta_analyse.headless_service
  -- --execute --port PORT
```

This is one argument vector (line wrapping above is descriptive). RootDriver
provides a fresh private operation cache in `UNIFIED_PRIVATE_CACHE_ROOT`; the
bootstrap makes a new subcache and sets actual `sys.pycache_prefix` **before any
Meta package import**. It inserts the explicit source root without site or .pth
processing. No dependency-root is needed by this stdlib-only adapter.

The service independently checks isolation/no-site/no-bytecode-write flags,
fresh empty subcache under the private parent and outside the source capsule,
and package/core/adapter import/cache origins. An entry module cannot authenticate
its own loader if malicious bytecode was already executed; the initial pinned
bootstrap and trusted interpreter belong to the **external owner trust boundary**.
Inherited cache settings are overridden by the owner and its bootstrap. Meta does
not create a competing bootstrap or weaken the initial import boundary.

The listener is fixed to `127.0.0.1`; no remote bind option exists. The profile
must supply:

| Environment field | Required binding |
| --- | --- |
| UNIFIED_MODULE_ID | `meta_analyse` exactly |
| UNIFIED_MODULE_VERSION | Declared semantic release version |
| UNIFIED_RELEASE_ID | Bounded owner release identity |
| UNIFIED_INSTANCE_TOKEN | Fresh owner-generated lowercase 64-hex nonce/token |
| UNIFIED_SOURCE_COMMIT | Exact admitted Meta 40-hex commit |
| UNIFIED_GIT_EXECUTABLE | Absolute local pinned Git executable path |
| UNIFIED_GIT_SHA256 | Independently provisioned Git executable SHA256 |
| UNIFIED_PRIVATE_CACHE_ROOT | Fresh owner operation cache, private 0700 on POSIX |

Unified RootDriver issues the first four identity fields and private cache; the
source commit and Git pins belong to its separately verified per-program environment. Do not publish the token or
invent a release/source pin. The token proves possession within the private
owner boundary; this loopback bearer transport is not remote TLS enrollment or
publisher authentication. The declared version is bound to the admitted owner
release profile; source consistency does not independently authenticate a version.

Use the actual immutable source capsule from the release materializer and a
trusted Python runtime and fresh-cache isolated bootstrap described above. Before binding,
the service checks its actual package repository root, exact HEAD, index tree,
every tracked raw file byte, source file types, and the pinned Git executable.
It rejects linked/reparse source and Git metadata, alternate objects (including HTTP alternates), replacement
refs, partial-clone/promisor lazy-fetch configuration, external Git worktrees,
include/filter configuration, environment repository
overrides and untracked executable source. Limits include 4096 tracked files,
32 MiB tracked content, and bounded Git subprocess output/deadlines.

Canonical capsule `core.attributesFile` and `core.hooksPath` may reference only
`os.devnull`; `core.fsmonitor` must be false if present. No source clean/filter
command, textconv, custom diff or status command is run. Git lazy fetching and
terminal prompting are disabled; source validation never requests remote objects. Source comparison is
**RAW_IDENTICAL only**, without CRLF normalization, attribute exemptions or
filename allowlists. Ordinary autocrlf desktop checkouts may refuse startup;
materialize canonical raw bytes instead of weakening the check. The current
uncommitted developer checkout intentionally cannot report source-qualified
readiness. Portable lexical/metadata checks do not claim native confinement
against concurrent filesystem namespace replacement.

Startup runs a small real deterministic core-level arithmetic self-check. That
check is synthetic and proves no market availability or numerical research
qualification. Runtime requests revalidate the source snapshot; source failure
prevents readiness/result publication. Health-probe latency and native Windows
shutdown behavior still require the exact hosted/native qualification profile.

## Private owner routes

Every accepted route requires one exact `Authorization: Bearer TOKEN` header.
Duplicate auth, forged tokens, nonlocal/duplicate Host, and any Origin are denied.
Host must match `127.0.0.1:PORT` or `localhost:PORT`; there is no browser CORS path.
Queries and unsupported methods are rejected. No token goes into logs, URLs,
analysis results, diagnostics or persistent files. It is returned only in the
owner-authenticated five-field health response required by RootDriver.

- `GET /internal/v2/module/health` returns exactly `module_id`, `version`,
  `release_id`, `instance_token`, `ready`. It reports ready only after source
  consistency and startup numerical checks. It does not grant fleet authority.
- `POST /internal/v1/history/analyze` accepts exactly `{payload, decision_ms}`
  as UTF-8 `application/json`. The payload is the existing Grid v1.1 export,
  including its original dataset/source receipts. The response is the actual
  existing adapter result, preserving causal decision-time row exclusion,
  unavailable/gap/partial status, original source fields and units. Integrity
  failure or authority forgery yields no result.

JSON duplicate fields and nonfinite constants fail. Exactly one bounded
Content-Length is required for POST; Transfer-Encoding is rejected. The body
limit is 8 MiB; the existing adapter limits rows to 2000 and enforces finite data,
market/source schema, clocks and hashes. Responses are bounded to 16 MiB. At
most four request threads and eight backlog connections are admitted; overload
receives unavailable without data. A three-second absolute connection I/O timer
closes sockets even under trickled headers, bodies or slow response consumers.
There are no retries, background feed loops or stored jobs. Closed sockets and
source/Git subprocess resources are cleaned up; SIGINT/SIGTERM request an orderly
local stop. Native Windows process control is not qualified by Linux tests.

The existing untouched-level algorithm may perform quadratic work on a maximum
prefix. Row/body/thread limits bound the work; they do not establish physical
capacity, hard real-time computation deadlines or a global quota scheduler.

The transport rejects backend contract drift: schema must remain
`meta.grid.history.analysis.v1`, quality must remain UNKNOWN, source authenticity
must remain NOT_EVALUATED, and execution/training/trading flags must each be
exactly false. A forged backend flag is rejected with no analysis result, never
rewritten into a false flag and returned as success. Honest results are unchanged.
Results retain `source_authenticity=NOT_EVALUATED` and false execution, training
and trading authorization. A valid digest is not authenticated market evidence;
`HISTORICAL` remains a producer label. No raw trades, order book, complete market
coverage, strategy profit, paper session, global task deduplication, HA or live
execution is reconstructed from OHLCV history.

## Verification scope

The real HTTP tests require the actual coordinated Unified checkout via
`UNIFIED_SOURCE_ROOT` (default sibling `unified-system`), including its pinned raw
bootstrap. Missing bootstrap fails the tests rather than becoming a skip or a
replacement launcher. Tests create a disposable clean Git capsule containing the actual new
service and existing core/adapter files, pin its actual commit and Git binary,
launch a real subprocess/HTTP listener, compare responses with the actual adapter,
and exercise auth/forgery/causality/source mutation/JSON bounds, trickled I/O,
slot exhaustion/recovery and process stop. They make only loopback connections.
They do not claim a real producer capture, remote identity or physical execution.
Native Windows and exact-release hosted tests remain separate evidence.

The main Linux/Windows and commissioning lanes checkout Unified
`d065537d880295282eb2a157579813958417407e` into ignored
`.source/unified-system`, verify its actual HEAD, and set `UNIFIED_SOURCE_ROOT`.
Pytest remains bounded to the existing `tests` catalog; the dependency checkout
is not collected as Meta tests. No native case, full-suite gate or selector is
removed.
