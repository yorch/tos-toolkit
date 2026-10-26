# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Pre-1.0, diagnostic codes are stable but rules may be added, and a newly added
rule can turn a previously green build red. Pin a version in CI.

## [Unreleased]

## [0.2.2] — 2026-10-26

### Fixed

- **Registry gaps that caused correct code to be rewritten.** Building the futures
  studies, the review gate removed `RegularTradingStart`/`RegularTradingEnd`
  because the registry did not know them — ten `E072` warnings. They are real: the
  thinkorswim reference carries a page for each, and the official `GetTime` example
  is built on them. A registry gap became a code regression, which is the wrong
  direction for this project.

  Added, each with its reference URL recorded in the entry:
  `RegularTradingStart`, `RegularTradingEnd`, `GetTime`, `HasContractChangeEvent`.

- `ATR` was recorded as `documented` but has **no page in the reference index**
  (404, checked against the live site). Downgraded to `unverified`, with the
  substitute spelled out: `WildersAverage(TrueRange(high, close, low), len)`.
- `Root` likewise: no page at any `Functions/*` category. Downgraded, with a note
  not to rely on it.
- `TrueRange` now records its three-argument signature and the verified page.

### Notes

Verification method, recorded because it nearly produced a false alarm: the
reference index is a single-page app that answers **200 with an `error_404` shell**
for routes that do not exist. Real pages are ~345 KB; missing ones are 25 KB. The
date/time category is spelled `Date---Time` (three dashes), not `Date-Time` — the
latter 404s for every function in it.

### Added

- The repository now lints itself: `tos.toml` at the root points `targets` at the
  bundled templates, so `tos lint` works with no arguments here exactly as it does
  in a consumer repo. `just lint` and `just check` use it.
- `config.load(..., discover_from_cwd=False)` for callers that already hold a
  resolved config; the MCP profile override uses it.

### Fixed

- A profile override inside the MCP server re-discovered `tos.toml` from the
  working directory. Harmless until this repo gained its own `tos.toml`, at which
  point `tos_lint` with `profile: "loose"` inherited the repository's header
  requirements. Two MCP tests caught it.

### Fixed

Documentation corrected against the code, found by an adversarial audit:

- `configuration.md` claimed `tos --profile loose lint` with no `tos.toml` exits 0.
  It exits 2: an empty run is not a pass.
- The MCP section overstated three things — findings use `path` and include
  `message`; an unavailable parser returns `isError: true` rather than "reporting
  unavailable"; and each malformed request gets a distinct JSON-RPC error code
  (`-32700`/`-32600`/`-32601`/`-32602`), not one.
- Rule gating was described wrongly: `E050` *is* gated by header mode, `E031` and
  `W050` are not but need the key they read, and artifact rules infer the kind from
  the configured directory so they never need `@kind`.
- `--profile loose` was described as "language rules only", which ignores that a
  project's own `tos.toml` applies on top; said so in the README, Agents page and
  adoption guide.
- `README` now lists `tos mcp` and links the reference documents.
- `status`, `docs`, `new` and `init` had no exit-code statements.
- The Action's `paths` default of `.` walks the repository; documented, and vendor
  directories are now skipped so `.ts` files under `node_modules` no longer fail CI.
- `tos review` accepts `paths` only with `--mode files`, and now fails closed when
  the selection exceeds the size budget instead of reviewing a subset.

### Fixed (code)

- `tos init` runs even when `tos.toml` is unparseable — it is the command you use to
  repair the project. An unknown `--profile` is rejected before anything is written.
- A notification with no `method` no longer receives a response.
- `tos status` prints every observed status, including ones added via `tos.toml`.
- `tos review --mode files` exits 2 rather than reviewing a subset when files exceed
  the size budget; diff mode names the files it could not inline.
- Scans skip vendor and build directories (`.git`, `.venv`, `node_modules`,
  `site-packages`, `build`, `dist`, `site`).

### Changed (tests)

`tests/test_docs_coverage.py` was weaker than it claimed, which the audit proved:
it silently skipped `syntax-check` (the handler is `_cmd_syntax`, not
`_cmd_syntax_check`), and its MCP argument check matched `paths`/`profile`/`strict`
in the Action's table rather than the MCP tool's own row. It now resolves handlers
through the COMMANDS table and fails when it cannot, checks flags and arguments
inside the relevant section or table row, requires a numeric exit code per command,
requires each JSON-RPC error code to be documented, and reads config keys from
`config.py` as well as the profile files.

### Added

- `docs/commands.md` now documents `tos mcp` (it was only on the Agents page), the
  full `--json` payload, and `syntax-check --allow-empty`.
- `docs/agents.md` documents each MCP tool's arguments and the Action's
  `artifact-name` input.
- `docs/configuration.md` documents the remaining `[header]` keys (`required`,
  `optional`, `statuses`, `assets`, `timeframes`, `panels`).
- `tests/test_docs_coverage.py` enumerates the real surface — subcommands, flags,
  MCP tools and their arguments, Action inputs, diagnostic codes, `tos.toml` keys —
  and fails when one is undocumented.

### Removed

- `tos explain --category` and `tos mcp --stdio`: both were accepted and ignored.
  A flag that changes nothing is worse than a missing one, because it implies a
  choice the tool does not offer. The new dead-flag test caught the second one.

### Fixed

- A `script { … }` block no longer confuses the secondary-aggregation rule, and
  `plot Scan;`-style declarations are no longer reported as bare assignments
  (see 0.2.0 notes).

## [0.2.1] — 2026-10-26

### Fixed

- `__version__` was a hand-maintained string and did not follow the
  `pyproject.toml` bump, so the 0.2.0 wheel reported `0.1.0` from `tos --version`
  and from the MCP `serverInfo` handshake. It is now read from the installed
  distribution metadata, so it cannot drift again. 0.2.0 is burned on PyPI;
  this is the corrected release.

## [0.2.0] — 2026-10-25

### Added

- **`tos mcp`** — serves the toolkit over the Model Context Protocol on stdio, so
  coding assistants call `tos_lint`, `tos_explain`, `tos_docs` and
  `tos_syntax_check` as native tools. No dependencies; MCP's stdio transport is
  JSON-RPC, so no SDK is required. `isError` is reserved for operational failures
  — findings come back as data.
- **GitHub Action** at `.github/actions/lint` — installs a pinned version, lints,
  emits inline `file:line` annotations, and publishes `errors`, `warnings` and the
  findings JSON as outputs and an artifact.
- `docs/agents.md` — the three integration paths, with the limits spelled out.
- `tos lint --json` now reports `ok`, `targets_found`, `error_count`,
  `warning_count` and `files_checked` alongside the findings.
- `tos lint --allow-empty` for a freshly scaffolded project.

### Fixed

- An empty run no longer reports success. Zero files checked (no targets, or no
  `.thinkscript` files) exits 2 with `"ok": false`, because a gate that silently
  checks nothing is indistinguishable from a passing one.
- Artifact restrictions now infer the kind from the configured directory when a
  file has no `@kind`, so `loose` on a headerless corpus still catches a scan
  calling `AddLabel`.
- MCP: a profile override no longer discards an explicit `--config`; stray `.ts`
  files are reported as `E005` instead of being silently dropped; malformed
  `params` or `name` return `INVALID_PARAMS` instead of killing the server; and
  notifications never receive a response.
- `[project] targets` must be an array of strings; a bare string used to become
  one target per character.
- Action: capture lint failure explicitly (GitHub runs composite bash with `-e`),
  add an `artifact-name` input, and use a supported branding colour.
- Artifact kind is inferred from the configured directory when a file has no
  `@kind`, when the declared kind is unrecognised, and for nested configurations
  like `kind_dirs = { scan = "src/scans" }` (longest prefix wins) and `"."` (root).
- `E406` — a scan exposing more than one plot. Schwab's scanner specifies one.
- A watchlist column may output an `AddLabel` instead of a `plot`; `E404` now only
  fires when a column has no output at all.
- `tos_explain` reports registry membership rather than asserting validity, and
  three unverified constants were removed from the registry
  (`Alert.ONCE_PER_BAR`, `PaintingStrategy.NUMBER`, `PaintingStrategy.LINE_VS_PREV`).
- `tos syntax-check` exits 2 when it checked nothing, like `lint`.
- `E407` — a scan reading a secondary aggregation (`AggregationPeriod`), which a
  chart supports and a Stock Hacker filter does not.
- `W402` now treats any nonzero numeric literal as always-true, matching
  ThinkScript's boolean conversion (`plot Scan = 2;` matched every symbol silently).
- `E403` requires that a scan exposes a `plot`, not that the plot is the final
  statement: `plot Scan; Scan = …;` is a documented form.
- MCP reports `ok: true` only when at least one file was actually analysed.
- `E407` also catches a positional aggregation argument
  (`close("SPY", AggregationPeriod.WEEK)`) and no longer misfires on a `period`
  parameter inside a `script` block or on an input named `period`.
- `E073` exempts any previously declared name, so the documented `def x;` +
  `x = …;` form is not reported as a bare assignment.

### Known limitations

- `E070`/`E071` do not analyse inside `script { … }` blocks, which have their own
  namespace. Documented in `docs/rules.md`.
- `AddArrow` is listed nowhere as valid: its existence is unverified.

## [0.1.0]

First release. Extracted from a private ThinkScript repository after the tooling
proved itself there — `E071` was found by a real failed paste, and the review gate
caught NaN-scale bugs in two studies before they shipped.

### Added

- **`tos lint`** with two layers of rules:
  - Layer 1 (always on): lexical hygiene, delimiter balance, case-insensitive
    identifier collisions, `rec` self-reference depth, unknown functions,
    `def`/`plot` namespace separation, and the platform's scan/column/strategy
    restrictions.
  - Layer 2 (profile-gated): `# @key:` header block, `@status` lifecycle,
    artifact kind vs directory, file naming, `@inputs` drift.
- **`tos syntax-check`** — grammar validation through the *real* thinkorswim
  parser, via a 59-line reflection shim compiled against the user's own
  installation. Exits 2 when the parser could not run (missing JDK, renamed
  classes, timeout), so a broken bridge can never look like a clean result.
- **`tos review`** — adversarial review harness, pinned to `codex` +
  `gpt-6.1-sol`. Refuses to run when lint reports errors. Substitute harnesses
  exit 3 so automation cannot mistake them for a gate pass.
- **`tos new`** and **`tos init`** — scaffolding from bundled templates, with
  project-local templates taking precedence.
- **`tos status`** — validation debt, counting missing and unknown `@status`
  values.
- **`tos docs`** and **`tos explain`** — the bundled ThinkScript knowledge base
  and a curated function registry with per-entry confidence levels.
- Two profiles: `strict` and `loose`. Every rule can be set to
  `off` / `warn` / `error` in `tos.toml`.
- 73 tests, including a regression fixture for each bug found in review.

### Notes

- No thinkorswim code is bundled, decompiled, or reimplemented. Names were
  observed read-only from a local install to seed the reference. See
  `docs/adr/0004-no-jar-redistribution.md`.
- `W090` and `E073` ship as warnings because they encode **unverified** platform
  behaviour. They become errors only after a paste-test confirms them.

[Unreleased]: https://github.com/yorch/tos-toolkit/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/yorch/tos-toolkit/compare/v0.1.0...v0.2.0
[0.2.1]: https://github.com/yorch/tos-toolkit/compare/v0.2.0...v0.2.1
[0.1.0]: https://github.com/yorch/tos-toolkit/releases/tag/v0.1.0
