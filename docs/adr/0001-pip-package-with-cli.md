# 0001 — Ship as a pip package with a `tos` CLI

- **Status:** Accepted
- **Date:** 2026-10-24

## Context

The tooling started life as `tools/*.py` inside one private trading repository:
a ~600-line linter, a scaffold script, a syntax checker, and a shell review
wrapper. A second and third ThinkScript repository would each need a copy.

Three ways to share it:

1. **Vendor the `tools/` directory into every repo.** No infrastructure at all.
   But every fix has to be copied N times, and the copies drift — the exact
   failure mode the "no module system" ADR was written to manage *within* a repo.
2. **A git submodule.** Shared updates, but submodules are friction for anything
   that needs a reproducible install, and `python3 tools/lint.py` paths leak
   everywhere.
3. **A pip package exposing a console script.** One install per machine, one
   command surface, versionable, and it can also register as a pre-commit hook.

The tool has no third-party Python dependencies, so packaging costs almost
nothing.

## Decision

Ship `tos-toolkit` as a pip-installable package whose only entry point is the
`tos` console script.

Consumers install from PyPI (`pipx install tos-toolkit`, `uv tool install
tos-toolkit`, or `pip install tos-toolkit`) or from git for an unreleased commit,
and call `tos` from a `justfile`.

## Consequences

- One source of truth; fixes propagate on reinstall.
- The command surface becomes public API. Renaming a subcommand is a breaking
  change, so commands are chosen conservatively.
- `tos init` exists because a package alone does not tell a new project what
  files it needs — the scaffold is part of the interface.
- We take on versioning discipline early (`0.1.0`, semver from here).
- The original repo keeps its scripts and its ADRs; only the reusable tooling
  moves. Migration is a follow-up, not part of this decision.
