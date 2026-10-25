# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Pre-1.0, diagnostic codes are stable but rules may be added, and a newly added
rule can turn a previously green build red. Pin a version in CI.

## [Unreleased]

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

[Unreleased]: https://github.com/yorch/tos-toolkit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yorch/tos-toolkit/releases/tag/v0.1.0
