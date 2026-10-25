# 0003 — Grammar checking is an optional extra

- **Status:** Accepted
- **Date:** 2026-10-24

## Context

`tos lint` can check structure, but it cannot answer "will this compile?" — only
thinkorswim's own parser can. That parser exists as Java classes inside the user's
installation, and calling it requires a JDK, the right jars, and a working
classpath across half a dozen jars plus a versioned install directory.

Two designs were available:

1. **Make the parser a hard dependency.** Every command needs thinkorswim and a
   JDK. Uniform behaviour, but the tool becomes useless on a laptop without ToS,
   in CI, or for anyone who just wants the linter.
2. **Make it optional.** The core is pure Python with no dependencies; the grammar
   check is an explicit extra with a clear failure mode.

Most of the value (header hygiene, collisions, unknown functions, artifact rules)
does not need the parser. Making everyone install a 2 GB trading platform to get a
linter is a bad trade.

## Decision

The grammar check is opt-in and isolated:

- It lives in `tos_toolkit/parser/bridge.py`, imports nothing heavy, and is only
  imported by `tos syntax-check`.
- It requires a local thinkorswim install (`[parser] tos_path`) and a JDK.
- When either is missing it prints an actionable message and exits **2** — a
  distinct code meaning "could not run", never 0 and never a false PASS.
- `[parser] enabled = false` disables it outright for CI.
- The `tos-toolkit[parser]` extra exists purely to make the requirement
  discoverable at install time; it adds no Python dependencies.

## Consequences

- `pip install tos-toolkit` works anywhere; `tos lint`, `tos status`, `tos new`,
  `tos init`, `tos docs`, `tos explain` need nothing but Python.
- CI without ToS cannot run grammar checks. Accepted: CI runs lint, and the
  grammar check is a documented local step.
- The bridge must handle a hostile environment: several ToS versions can be
  installed at once, macOS ships multi-arch `java`/`javac` stubs that resolve to
  the wrong architecture, and a JRE alone is not enough (the shim needs `javac`).
  The bridge therefore *probes* candidate binaries by executing them rather than
  trusting a path that exists.
- Grammar validity is still not correctness. The command prints "grammar only" in
  every run so nobody mistakes it for a semantic check.
