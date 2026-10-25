# 0002 — Layer 1 language rules vs Layer 2 profiles

- **Status:** Accepted
- **Date:** 2026-10-24

## Context

The linter grew inside one repository, so it encodes two different kinds of
knowledge without distinguishing them:

- **Language facts.** A scan cannot call `AddLabel`. Identifiers are
  case-insensitive, so `def pdHigh` and `plot PdHigh` collide. `//` is not a
  comment. A `rec` may self-reference only in limited ways.
- **House conventions.** Every file carries a `# @key:` header. `@status` moves
  `draft → validated` and only a human may promote it. Studies live in
  `studies/<category>/`.

Shipping both as one blob makes the tool unusable outside a repo that already
adopts our exact conventions: every foreign file fails the header check, the
directory check, and the `@inputs` check, and the genuinely useful language
findings are buried in noise.

The split also matters for correctness. The collision rule caught a real failed
paste; the header rule is a preference. They should not be equally removable.

## Decision

**A rule goes in Layer 1 (`checks/language.py`, `checks/artifacts.py`) if it is
true of ThinkScript anywhere. Otherwise it goes in Layer 2 (`checks/header.py`,
`checks/layout.py`) and is profile-gated.**

- Layer 1 is always on.
- Layer 2 reads `config.header_mode` and returns immediately when it is `off`.
- `layout.py` additionally requires the file to sit inside a *configured* kind
  directory, so a foreign corpus triggers nothing even under `strict`.

Two built-in profiles ship: `strict` (Layer 2 on) and `loose` (Layer 2 off).
Individual rules can be overridden to `off` / `warn` / `error` regardless of
profile.

## Consequences

- The tool is useful on codebases that share none of our conventions — the main
  reason it can be published at all.
- Contributors must decide which layer a new rule belongs to. The rule is stated
  in `docs/architecture.md` and `AGENTS.md`, and the default when unsure is
  Layer 2, because a wrong Layer 1 rule is a false positive for everyone.
- `header_mode` is a mode rather than a boolean because "header optional" (check
  it if present, don't demand it) is a genuinely useful middle ground for
  migrating an existing repo.
- Profiles are data (`data/profiles/*.toml`), so a consumer can copy one and
  tweak it without forking the code.
