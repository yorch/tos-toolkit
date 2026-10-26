# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Pre-1.0, diagnostic codes are stable but rules may be added, and a newly added
rule can turn a previously green build red. Pin a version in CI.

## [Unreleased]

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
[0.1.0]: https://github.com/yorch/tos-toolkit/releases/tag/v0.1.0
