# Project Guidelines

Guidance for AI agents working on **tos-toolkit** itself. This repo is a Python
tool; the ThinkScript files it analyses live in consumer repos, not here.

## What this is

A pip-installable CLI (`tos`) providing static analysis, scaffolding,
validation tracking, and adversarial review for ThinkScript code, plus a
ThinkScript knowledge base that agents should read before writing scripts.

## Read order

1. `AGENTS.md` (this file)
2. `docs/architecture.md` — the layered design, and why rules are split
3. `docs/adr/` — decisions that are expensive to reverse
4. `src/tos_toolkit/docs/knowledge-base/README.md` — ThinkScript reference

## Hard rules

- **Never bundle, decompile, or redistribute thinkorswim code.** See
  `docs/adr/0004-no-jar-redistribution.md`. The parser bridge invokes the user's
  own installation at runtime. Nothing from `thinkscript-*.jar` may enter this
  repo, not even a reconstructed grammar.
- **Layer discipline.** A rule that is true of ThinkScript anywhere goes in
  `checks/language.py` and is always on. A rule that encodes *our* house
  conventions goes in a profile and is opt-in. If you are unsure which layer a
  rule belongs to, it is a profile rule.
- **Diagnostic codes are stable API.** `E071` means one thing forever. Add new
  codes, never repurpose old ones.
- **No Python dependencies in the core.** The tool must run from a bare
  interpreter. Dev-only extras are fine.
- **Never claim a script compiles.** Only `tos syntax-check` with a real ToS
  install can report grammar validity, and even that says nothing about
  semantics.

## Layout

```text
src/tos_toolkit/
├── cli.py            command surface
├── config.py         tos.toml discovery + profile resolution
├── diagnostics.py    Finding / Report / exit codes
├── lexer.py          clean-room tokenizer + statement splitter
├── registry.py       function and constant lookup
├── checks/           language.py (generic), header.py, artifacts.py, layout.py
├── parser/           optional ToS jar bridge + Checker.java
├── review.py         adversarial review harness
├── scaffold/         templates + files written by `tos init`
├── docs/             knowledge base, shipped as package data
└── data/             functions.json, constants.json, profiles/*.toml
```

## Working style

- One coherent change per commit; keep diffs reviewable.
- Rules need tests. `tests/test_checks.py` has a fixture per code.
- When a rule produces a false positive on the user's real repos, fix the rule
  or add an escape hatch — do not weaken the diagnostic to a comment.
