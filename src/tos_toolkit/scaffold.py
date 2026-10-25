"""Scaffolding: one file (`tos new`) or a whole project (`tos init`)."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "scaffold" / "templates"
PROJECT_DIR = PACKAGE_DIR / "scaffold" / "project"

SNAKE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")
STUDY_CATEGORIES = ["trend", "momentum", "volatility", "volume", "structure"]


def _titleize(stem: str) -> str:
    return " ".join(word.capitalize() for word in re.split(r"[_\-\s]+", stem) if word)


def _resolve_kind(config, arg: str, rest: list[str]) -> tuple[str, Path]:
    lowered = arg.lower()
    kind_dirs = config.kind_dirs

    if lowered in kind_dirs:
        if not rest:
            raise SystemExit(
                f"error: missing path after kind '{lowered}' (e.g. {lowered} trend/my_indicator)"
            )
        return lowered, Path(rest[0])

    first = Path(arg).parts[0]
    kind_by_dir = {directory: kind for kind, directory in kind_dirs.items()}
    if first in kind_by_dir:
        return kind_by_dir[first], Path(*Path(arg).parts[1:])

    raise SystemExit(
        f"error: cannot infer kind from '{arg}'. "
        f"Pass a kind ({', '.join(sorted(kind_dirs))}) or a path under one of "
        f"{', '.join(sorted(kind_dirs.values()))}"
    )


def new_file(config, kind_or_path: str, path: str | None, name: str | None) -> int:
    kind, rel = _resolve_kind(config, kind_or_path, [path] if path else [])

    if rel.suffix and rel.suffix != ".thinkscript":
        raise SystemExit(
            f"error: refusing to create '{rel}'; extension must be .thinkscript"
        )
    if rel.suffix == ".thinkscript":
        rel = rel.with_suffix("")

    template = TEMPLATE_DIR / f"{kind}.thinkscript"
    if not template.is_file():
        raise SystemExit(f"error: missing template for kind '{kind}'")

    target = config.root / config.kind_dirs[kind] / rel
    target = target.with_suffix(".thinkscript")
    if not target.resolve().is_relative_to(config.root.resolve()):
        raise SystemExit(f"error: refusing to write outside the project: {target}")
    if target.exists():
        raise SystemExit(f"error: {target} already exists; not overwriting")

    stem = target.stem
    if not SNAKE.match(stem):
        raise SystemExit(f"error: file name '{stem}' must be lower_snake_case")

    body = template.read_text(encoding="utf-8").replace("__NAME__", name or _titleize(stem))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")

    print(f"created {target}")
    print()
    print("next:")
    print(f"  1. edit    {target}")
    print("  2. lint    tos lint")
    print("  3. review  tos review --mode files " + str(target))
    print("  4. paste into thinkorswim, then set '@status: validated' by hand")
    return 0


_TOS_TOML = """\
# tos-toolkit configuration.
# Resolved on top of the built-in profile below. Every rule can be overridden
# in [checks] as "off" | "warn" | "error".

[profile]
name = "{profile}"

[project]
targets = ["studies", "scans", "strategies", "columns", "templates"]
templates_dir = "templates"

[header]
mode = "{header_mode}"

[parser]
# `tos syntax-check` needs a local thinkorswim install + a JDK.
# Everything else works without it.
enabled = true
tos_path = "/Applications/thinkorswim"

[review]
harness = "claude"          # "claude" (larger context) or "codex"
model = "claude-opus-5-5"
effort = "high"

[checks]
# Unknown function names are the most common ThinkScript mistake.
unknown_functions = "warn"
"""

_JUSTFILE = """\
set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Static analysis (no thinkorswim required)
lint:
    @tos lint

# Validation debt: which scripts still need a paste-test
status:
    @tos status

# Grammar check via a local thinkorswim install (optional)
syntax:
    @tos syntax-check

# Scaffold a file:  just new study trend/ema_cloud_flip
new *args:
    @tos new {{args}}

# Adversarial review of uncommitted changes
review:
    @tos review --mode diff

# Whole-repo sweep
audit:
    @tos review --mode audit
"""

_AGENTS_SECTION = """\

## ThinkScript conventions (tos-toolkit)

This repo uses [`tos-toolkit`](https://pypi.org/project/tos-toolkit/) for static
analysis. Read the bundled knowledge base before writing scripts:

```bash
tos docs --list          # topics
tos docs gotchas         # NaN, rec rules, platform limits
tos explain TrueRange    # is this function real?
```

Commands:

```bash
tos lint                 # structural checks
tos status               # which scripts are still draft
tos syntax-check         # real grammar check (needs a local thinkorswim install)
tos new study trend/foo  # scaffold from template
tos review --mode diff   # adversarial review gate
```

Non-negotiables:

- File extension is `.thinkscript`, never `.ts` (collides with TypeScript).
- Never invent a ThinkScript function. If `tos explain` does not know it, verify
  it in the platform first.
- `@status` starts at `draft`. Only a human who has pasted the script into
  thinkorswim and seen it render may set `validated`.
- Guard every division. `NaN` is contagious and comparisons against it are
  silently false.
"""

_GITIGNORE = """\
.DS_Store
__pycache__/
.review/
dist/
"""


def _write(path: Path, body: str, force: bool) -> bool:
    if path.exists() and not force:
        print(f"  skip (exists): {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    print(f"  wrote: {path}")
    return True


def init_project(root: Path, profile: str = "strict", force: bool = False) -> int:
    from .config import KIND_DIRS_DEFAULT

    header_mode = "off" if profile == "loose" else "required"

    print(f"Initialising tos-toolkit project in {root} (profile={profile})")

    _write(root / "tos.toml", _TOS_TOML.format(profile=profile, header_mode=header_mode), force)

    # kind directories (+ study categories)
    for kind, directory in KIND_DIRS_DEFAULT.items():
        base = root / directory
        if kind == "study":
            for category in STUDY_CATEGORIES:
                (base / category).mkdir(parents=True, exist_ok=True)
                (base / category / ".gitkeep").touch()
        else:
            base.mkdir(parents=True, exist_ok=True)
            (base / ".gitkeep").touch()
    print(f"  created artifact directories: {', '.join(KIND_DIRS_DEFAULT.values())}")

    # templates
    templates = root / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    for template in TEMPLATE_DIR.glob("*.thinkscript"):
        target = templates / template.name
        if not target.exists() or force:
            shutil.copy2(template, target)
    print(f"  copied templates -> {templates}")

    (root / "docs" / "adr").mkdir(parents=True, exist_ok=True)
    _write(root / "docs" / "validation.md", _validation_doc(), force)

    _write(root / "justfile", _JUSTFILE, force)
    _write(root / ".gitignore", _GITIGNORE, force)

    agents = root / "AGENTS.md"
    if agents.exists():
        text = agents.read_text(encoding="utf-8")
        if "tos-toolkit" not in text:
            agents.write_text(text + _AGENTS_SECTION, encoding="utf-8")
            print(f"  appended to: {agents}")
        else:
            print(f"  skip (already mentions tos-toolkit): {agents}")
    else:
        agents.write_text("# Project Guidelines\n" + _AGENTS_SECTION, encoding="utf-8")
        print(f"  wrote: {agents}")

    print()
    print("next:")
    print("  1. tos lint")
    print("  2. tos new study trend/my_first_indicator")
    print("  3. paste it into thinkorswim")
    return 0


def _validation_doc() -> str:
    return """\
# Validation

There is no compiler you can run headlessly, so validation is a human protocol.

`tos lint` catches structure and `tos syntax-check` catches grammar. Neither can
tell you whether a formula is right, and neither can tell you a study renders.

## The paste protocol

For each script and each asset class × timeframe you care about:

1. Copy the file (header comments included).
2. thinkorswim → Studies → Edit Studies → Create (or Scanner → Add filter → Study → Custom).
3. Paste, name it exactly as `@name`, apply.
4. Read any error dialog literally; it names the offending token.
5. Apply to a real chart of the intended asset class and timeframe.
6. Sanity-check: does anything render? Are values in a plausible range? Does a
   known event appear where it should? Scrub to the left edge — do the first bars
   degrade gracefully or throw?
7. Record the result below.

## If you change anything

Any behavioural edit to a `validated` script reverts it to `draft` until it is
pasted again. Comment-only edits are exempt. This is the only thing that keeps
`@status` honest.

## Definition of done

- `tos lint` exits 0.
- `tos review` has run; findings fixed or explicitly waived.
- The script has been pasted into thinkorswim and rendered with zero errors.
- `@status` is `validated`, set by hand.
- The header still describes what the script actually does.

## Log

| Date | Script | Ver | Asset | TF | Result | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | nothing validated yet |
"""
