# 0004 — No thinkorswim code is bundled or reverse engineered

- **Status:** Accepted
- **Date:** 2026-10-24

## Context

We wanted the grammar check to work without a local install. We investigated what
the shipped jars would give up, read-only:

- The parser is **JavaCC-generated** (`thinkscript-parser-*.jar` →
  `...script.javacc.TosScript`). All grammar rule names are recoverable from
  method names (`declare_statement`, `plot_declaration`, `rec_def_statement`,
  `fold_statement`, `if_expression`, `switch_statement`, `within_expr`, …).
- The complete **token set** is recoverable from `TosScriptConstants`, and it
  revealed language features that no public documentation we had mentioned
  (`switch`/`case`/`default`, `profile`, `reference`, `within`, `ago`).
- A partial **function registry** is recoverable by scanning class string
  literals (~388 candidates across jars).
- The jars are **signed** (`META-INF/TOSPROD.SF`, `TOSPROD.RSA`) but not
  obfuscated.

So a faithful reimplementation is a few weeks of work, not a research project.

## Decision

**No part of thinkorswim is bundled, decompiled, or redistributed.**

1. **No jar redistribution.** The jars are proprietary Schwab software licensed
   for use with their platform. They never enter this repository.
2. **No decompiled or reconstructed grammar in the repo.** Decompiling to rebuild
   the parser produces a derivative work. Committing it would be the single
   riskiest thing this project could do and would taint any future release.
3. **The lexer is hand-written from public documentation.** It is a *faithful*
   tokenizer, not an equivalent parser; it splits statements, tracks bracket
   depth, drops comments, and preserves line numbers.
4. **Grammar validation is delegated to the user's own installation** through the
   reflection shim in `parser/java/Checker.java`. The shim contains no Schwab code
   and compiles against jars that already exist on the user's machine.
5. **Names may inform our own documentation.** Token names, rule names and
   function names are functional interface facts, not creative expression. They
   are used as a *completeness checklist* for the knowledge base, and anything
   inferred that way is marked unverified. We do not infer semantics from them.

## Consequences

- The published package contains only our code, our data, and our documentation —
  a clean legal position.
- Users without thinkorswim cannot run `tos syntax-check`. Documented in the README
  and enforced by exit code 2.
- The reflection shim is inherently coupled to internal class names. A ToS update
  could rename them and break the bridge. Accepted: the failure is loud
  (`RESULT:` missing → exit 2), never a silent PASS.
- The `tos docs` knowledge base covers features our reference material got wrong
  or omitted, including a dedicated `unverified-tokens` topic listing keywords we
  know exist but have never tested.
- If a standalone parser is ever wanted, it must be written **clean room** from
  public documentation. That is a separate project with its own ADRs, not a change
  to this one.
