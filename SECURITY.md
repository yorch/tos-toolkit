# Security Policy

## Scope

`tos-toolkit` is a local developer tool. It reads ThinkScript files, writes
scaffolded files into the directory you run it in, and can invoke two external
programs (`codex` or `claude`) when you ask for a review.

The realistic risk surface is:

1. **Arbitrary file read/write** via a crafted path or a scaffold target.
2. **Command execution** via the review harness or the parser bridge.
3. **Information disclosure** — source code sent to a model provider during
   `tos review`.

## Design decisions that limit exposure

- `tos new` refuses to write outside the project root and refuses to overwrite.
- `tos review` sends code to a model provider. That is the point of the command,
  but it means **your code leaves the machine**. Be precise about what is sent:
  - `--mode diff`: the git status, both diffs, **and the full contents of every
    untracked, non-ignored file**, of any type, up to ~400k characters. An
    un-ignored `.env` would be included. Check `git status` first.
  - `--mode audit`: every `.thinkscript` file in the repo.
  - `--mode files`: the files or directories you name.
  - The reviewer process also runs with read tools and can read other files in the
    repository on its own initiative.

  Do not run it on code you are not permitted to share.
- The parser bridge compiles and runs a small shim against jars you already have.
  It does not download anything and does not modify your thinkorswim install.
- No network access anywhere except the review harness.
- The grammar shim compiles into the package directory, or an owner-only per-user
  cache (`$XDG_CACHE_HOME/tos-toolkit/shim`, mode 0700) when the package is
  read-only. It refuses to trust a cache owned by another user.

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's private advisory flow:

<https://github.com/yorch/tos-toolkit/security/advisories/new>

Include:

- the version (`tos --version`) and platform,
- a minimal reproduction,
- what an attacker gains.

Expect an acknowledgement within a few days. This is a personal project with no
funding, so there is no bug bounty — but credit in the advisory if you want it.

## Supported versions

Only the latest released version is supported. The project is pre-1.0 and rules
still change.
