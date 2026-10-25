"""Header-block rules — profile-gated.

Only runs when ``[header] mode`` is ``required`` or ``optional``. A repo with no
header convention sets ``mode = "off"`` and these rules disappear entirely.
"""

from __future__ import annotations

import re

from ..diagnostics import Finding

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def check(ctx) -> list[Finding]:
    mode = ctx.config.header_mode
    if mode == "off":
        return []

    out: list[Finding] = []
    if not ctx.header:
        if mode == "required":
            out.append(
                ctx.finding(
                    "E101",
                    1,
                    "missing header block",
                    hint="Start the file with '# @name:', '# @kind:', '# @status:' ...",
                )
            )
        return [item for item in out if item is not None]

    out.extend(_required_keys(ctx))
    out.extend(_values(ctx))
    out.extend(_unknown_keys(ctx))
    out.extend(_version(ctx))
    out.extend(_inputs(ctx))
    out.extend(_asset_consistency(ctx))
    return [item for item in out if item is not None]


def _required_keys(ctx) -> list[Finding]:
    out = []
    for key in ctx.config.required_keys:
        if not ctx.header.get(key):
            out.append(
                ctx.finding("E102", 1, f"header missing required '@{key}'")
            )
    return [item for item in out if item is not None]


def _split_list(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def _values(ctx) -> list[Finding]:
    out: list[Finding] = []
    config = ctx.config

    status = ctx.header.get("status", "").strip().lower()
    if status and status not in config.statuses:
        out.append(
            ctx.finding(
                "E103",
                1,
                f"@status '{status}' is not one of {sorted(config.statuses)}",
            )
        )

    kind = ctx.header.get("kind", "").strip().lower()
    if kind and kind not in config.kind_dirs:
        out.append(
            ctx.finding(
                "E103", 1, f"@kind '{kind}' is not one of {sorted(config.kind_dirs)}"
            )
        )

    panel = ctx.header.get("panel", "").strip().lower()
    if panel and panel not in config.panels:
        out.append(
            ctx.finding(
                "E103", 1, f"@panel '{panel}' is not one of {sorted(config.panels)}"
            )
        )
    if kind in {"scan", "column"} and panel and panel != "none":
        out.append(
            ctx.finding(
                "E103",
                1,
                f"@kind '{kind}' has no panel; expected '@panel: none' (got '{panel}')",
            )
        )

    for asset in _split_list(ctx.header.get("assets", "")):
        if asset not in config.assets:
            out.append(
                ctx.finding(
                    "E103", 1, f"@assets contains unknown class '{asset}'"
                )
            )

    for timeframe in _split_list(ctx.header.get("timeframes", "")):
        if timeframe not in config.timeframes:
            out.append(
                ctx.finding(
                    "E103", 1, f"@timeframes contains unknown value '{timeframe}'"
                )
            )
    return [item for item in out if item is not None]


def _asset_consistency(ctx) -> list[Finding]:
    """A script that calls option functions must declare the `option` asset.

    The registry carries a category per function, so this stays in sync as the
    registry grows instead of hard-coding a function list.
    """
    declared = set(_split_list(ctx.header.get("assets", "")))
    if not declared:
        return []

    from ..lexer import Kind

    seen: set[str] = set()
    out: list[Finding] = []
    for statement in ctx.statements:
        tokens = statement.tokens
        for index, token in enumerate(tokens[:-1]):
            if token.kind is not Kind.IDENT or tokens[index + 1].kind is not Kind.LPAREN:
                continue
            if index > 0 and tokens[index - 1].kind is Kind.OP and tokens[index - 1].value == ".":
                continue
            if token.lower in seen:
                continue
            seen.add(token.lower)
            info = ctx.registry.function(token.lower)
            if info is None:
                continue
            if info.category in {"option", "future"} and info.category not in declared:
                out.append(
                    ctx.finding(
                        "E050",
                        token.line,
                        f"uses {token.value}() but @assets does not declare "
                        f"'{info.category}'",
                    )
                )
    return [item for item in out if item is not None]


def _unknown_keys(ctx) -> list[Finding]:
    known = set(ctx.config.required_keys) | set(ctx.config.optional_keys)
    out = []
    for key in ctx.header:
        if key not in known:
            out.append(
                ctx.finding("W101", 1, f"unknown header key '@{key}'")
            )
    return [item for item in out if item is not None]


def _version(ctx) -> list[Finding]:
    version = ctx.header.get("version", "").strip()
    if version and not SEMVER.match(version):
        return [
            ctx.finding("W102", 1, f"@version '{version}' is not semver (x.y.z)")
        ]
    return []


def _inputs(ctx) -> list[Finding]:
    """@inputs must match the actual input statements, in order."""
    actual = [
        match.group(1)
        for match in re.finditer(
            r"^\s*input\s+([A-Za-z_][A-Za-z0-9_]*)\s*=", ctx.text, re.MULTILINE
        )
    ]
    documented_raw = [
        chunk.strip() for chunk in ctx.header.get("inputs", "").split(",") if chunk.strip()
    ]
    documented = [chunk.split("=")[0].strip() for chunk in documented_raw]

    out: list[Finding] = []
    if actual and not documented:
        out.append(
            ctx.finding(
                "E104",
                1,
                f"@inputs is missing: {', '.join(actual)}",
                hint="Document every input so readers can tune without reading the body.",
            )
        )
        return [item for item in out if item is not None]

    if documented and not actual:
        out.append(
            ctx.finding(
                "W103", 1, "@inputs documents inputs that do not exist"
            )
        )
        return [item for item in out if item is not None]

    missing = [name for name in actual if name not in documented]
    extra = [name for name in documented if name not in actual]
    if missing:
        out.append(ctx.finding("E104", 1, f"@inputs missing: {', '.join(missing)}"))
    if extra:
        out.append(
            ctx.finding(
                "W103", 1, f"@inputs documents non-existent inputs: {', '.join(extra)}"
            )
        )
    if not missing and not extra and documented != actual:
        out.append(
            ctx.finding(
                "W104",
                1,
                "@inputs order does not match the input statements",
                hint="@inputs should list them in declaration order.",
            )
        )
    return [item for item in out if item is not None]
