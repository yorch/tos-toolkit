# Contributing

Small project, one maintainer, strong opinions. Read this before a large PR.

## Setup

```console
$ git clone https://github.com/yorch/tos-toolkit
$ cd tos-toolkit
$ python -m venv .venv && . .venv/bin/activate
$ pip install -e ".[dev]"
$ python -m pytest -q
```

The package has **no runtime dependencies**. Please keep it that way — a linter
that needs a dependency tree is a linter people skip.

## The one design rule

> A rule belongs to **Layer 1** if it is true of ThinkScript anywhere.
> Otherwise it belongs to **Layer 2** and must be profile-gated.

This is what makes the tool usable on repositories that share none of our
conventions. When unsure, choose Layer 2: a wrong Layer 1 rule is a false
positive for every user.

See [`docs/adr/0002`](docs/adr/0002-layered-core-and-profiles.md) and
[`docs/architecture.md`](docs/architecture.md).

## Adding a rule

1. Pick a new code. Ranges are documented in `docs/rules.md`. **Codes are API** —
   never repurpose an existing one.
2. Add the default severity to `DEFAULT_LEVELS` in `checks/__init__.py`.
3. Implement it in the correct module: `language.py`, `artifacts.py`,
   `header.py`, or `layout.py`.
4. Add the code to the table in `docs/rules.md`.
5. Add a test in `tests/test_checks.py` — one fixture that must fire, and
   ideally one that must not.

## Honesty rules

These are not style preferences; they are the project's reason to exist.

- **Never claim a script compiles.** Only `tos syntax-check` against a real
  installation can say anything about grammar, and even that says nothing about
  semantics.
- **Never state an unverified platform behaviour as fact.** If you have not
  pasted it into thinkorswim, mark it unverified and make the rule a warning, not
  an error. `W090` and `E073` are examples of rules kept at `warn` for exactly
  this reason.
- **Never bundle thinkorswim code.** No jars, no decompiled output, no
  reconstructed grammar. See [`docs/adr/0004`](docs/adr/0004-no-jar-redistribution.md).
  A PR that adds any of these will be closed.

## Documentation

- User-facing pages live in `docs/` and are published to GitHub Pages.
- The ThinkScript reference lives in `src/tos_toolkit/docs/knowledge-base/` and is
  shipped inside the package so `tos docs` works everywhere. It is staged into
  `docs/knowledge-base/` at build time — that copy is gitignored, never edit it.

Build the site locally:

```console
$ pip install -r docs/requirements.txt
$ python scripts/sync_kb_docs.py
$ mkdocs serve
```

CI builds with `mkdocs build --strict`, so a broken internal link fails the build.

## Commits and PRs

- One coherent change per PR; keep diffs reviewable.
- Conventional-ish subject lines (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Update `CHANGELOG.md` under `## [Unreleased]`.
- Fill in the PR template, including the verification checkboxes.

## Review

Maintainer-side, the project uses an adversarial review gate: a model is asked to
assume the author is wrong and hunt for specific ThinkScript failure modes. If you
want to run it yourself and you have the `codex` CLI:

```console
$ tos review --mode diff
```

Its findings are claims to check, not verdicts. Say so if you disagree — with
evidence.

## Reporting bugs and asking for rules

Open an issue using the templates. The most useful thing you can attach is a
**minimal `.thinkscript` file** that reproduces the problem. Do not paste
proprietary indicators or account data; a synthetic snippet is just as good.

## License

MIT. By contributing you agree your work is licensed under the same terms.
