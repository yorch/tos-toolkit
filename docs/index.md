# tos-toolkit

Static analysis, scaffolding, and adversarial review for **ThinkScript**
(thinkorswim) code.

ThinkScript has no compiler you can run in CI, no package manager, and no module
system. This toolkit automates the parts that can be automated, and is explicit
about the part that cannot.

```console
$ tos lint                  # structural checks — no thinkorswim needed
$ tos syntax-check          # real grammar check — needs a local thinkorswim
$ tos review --mode diff    # adversarial AI review of your changes
```

Everything except `syntax-check` runs on a bare Python install with no
thinkorswim anywhere.

It also speaks **MCP**, so a coding assistant calls `tos_lint`, `tos_explain`
and `tos_docs` as native tools instead of shelling out — see
[Agents and CI](agents.md).

---

## What problem it solves

You write a study in thinkorswim, it fails to apply, and the error says
`Identifier Already Used: PdHigh`. Your `rec pdHigh` and your `plot PdHigh` are
the **same identifier**, because ThinkScript names are case-insensitive. Nothing
warned you, because there is no compiler you can run.

That exact failure is now `E071`. So are about thirty other ways a ThinkScript
file can be wrong before it ever reaches the platform.

---

## Install

```console
$ pipx install tos-toolkit     # or: uv tool install tos-toolkit
$ pip install tos-toolkit
```

Published on [PyPI](https://pypi.org/project/tos-toolkit/).

Requires Python 3.11+. The core has **zero** Python dependencies.

The optional grammar check needs a local thinkorswim install and a JDK:

```console
$ pip install "tos-toolkit[parser]"  # no extra dependencies; marks the requirement
```

No thinkorswim code is bundled, redistributed, or decompiled. The jars were
inspected read-only for names only — see
[ADR 0004](adr/0004-no-jar-redistribution.md).

---

## 60-second tour

```console
$ mkdir my-tos-scripts && cd my-tos-scripts
$ tos init
$ tos new study trend/ema_cloud_flip
$ tos lint
$ tos status
$ tos docs gotchas
$ tos explain TrueRange
```

`tos init` writes the artifact directories, copy-ready templates, a `justfile`, a
validation protocol, and a conventions section for `AGENTS.md`.

---

## Two layers

Mixing house conventions into a linter is what makes it unusable outside its
author's repo. So the rules are split:

| Layer | Examples | Gate |
| --- | --- | --- |
| **1 — language** | unbalanced delimiters, `//` is not a comment, identifier collisions, unknown functions, scan/column restrictions | always on |
| **2 — house style** | `# @key:` header block, `@status` lifecycle, `studies/<category>/` layout | `[header] mode` |

`[profile] name = "loose"` turns Layer 2 off entirely. Any single rule can be set
to `off`, `warn`, or `error`.

Details: [Rules](rules.md) · [Configuration](configuration.md).

---

## Honest limits

- **It cannot tell you a script works.** Only pasting it into thinkorswim and
  watching it render does.
- **`syntax-check` only checks grammar.** It will accept
  `FooBarNotAFunction(close)`. Function names are `lint`'s registry and
  `review`'s job.
- **The registry is curated, not exhaustive.** An unknown name is a prompt to
  verify, not a verdict.
- **The intended loop ends with a human:**

```text
tos lint  →  tos syntax-check  →  tos review  →  paste into ToS  →  @status: validated
```

---

## Unofficial

This project is not affiliated with, endorsed by, or supported by Charles Schwab
or thinkorswim. "thinkorswim" and "ThinkScript" are their trademarks, used here
only to describe what this tool analyses.
