"""Layout rules — kind vs directory, and file naming.

Fires only when the file actually lives inside a configured kind directory, so
pointing the toolkit at an arbitrary corpus never triggers these.
"""

from __future__ import annotations

import re

from ..diagnostics import Finding

SNAKE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")
SUFFIX_BY_KIND = {"scan": "_scan", "strategy": "_strat", "column": "_col"}


def check(ctx) -> list[Finding]:
    # Layer 2: directory and naming conventions are house style. With headers
    # off there is no declared kind to compare against, and the project has said
    # it does not want these conventions enforced.
    if ctx.config.header_mode == "off":
        return []
    out = _kind_matches_directory(ctx) + _naming(ctx)
    return [item for item in out if item is not None]


def _kind_matches_directory(ctx) -> list[Finding]:
    parts = ctx.rel.parts
    if not parts:
        return []
    kind_by_dir = {directory: kind for kind, directory in ctx.config.kind_dirs.items()}
    expected = kind_by_dir.get(parts[0])
    if expected is None:
        return []
    # Templates are starters, not artifacts: exempt from the kind check.
    if ctx.config.templates_dir and parts[0] == ctx.config.templates_dir:
        return []
    declared = ctx.header.get("kind", "").strip().lower()
    if declared and declared != expected:
        finding = ctx.finding(
            "E120",
            ctx.first_code_line or 1,
            f"@kind '{declared}' does not match directory '{parts[0]}/' "
            f"(expected '{expected}')",
        )
        return [finding]
    return []


def _naming(ctx) -> list[Finding]:
    parts = ctx.rel.parts
    if not parts:
        return []
    kind_by_dir = {directory: kind for kind, directory in ctx.config.kind_dirs.items()}
    kind = kind_by_dir.get(parts[0])
    if kind is None:
        return []

    out: list[Finding] = []
    stem = ctx.path.stem
    if not SNAKE.match(stem):
        out.append(
            ctx.finding("W080", 1, f"file name '{ctx.path.name}' is not lower_snake_case")
        )
    suffix = SUFFIX_BY_KIND.get(kind)
    if suffix and not stem.endswith(suffix):
        out.append(
            ctx.finding(
                "W081", 1, f"{kind} files should end with '{suffix}'"
            )
        )
    return [item for item in out if item is not None]
