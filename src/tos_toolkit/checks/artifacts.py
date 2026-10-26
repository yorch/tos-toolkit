"""Platform rules for scans, columns, and strategies.

These are Schwab's rules, not ours — a scan genuinely cannot call ``AddLabel``.
Always on, regardless of profile.
"""

from __future__ import annotations

from pathlib import Path

from ..diagnostics import Finding
from ..lexer import Kind
from .language import CHART_ONLY

# In watchlist columns, these two are supported; the rest are not.
# Comparisons are case-insensitive: ThinkScript identifiers are.
COLUMN_ALLOWED = {"addlabel", "assignbackgroundcolor"}
CHART_ONLY_LOWER = {name.lower() for name in CHART_ONLY}


def _kind_from_directory(ctx) -> str:
    """The artifact kind implied by the directory a file lives in.

    Compares whole path components, so a nested configuration such as
    ``kind_dirs = { scan = "src/scans" }`` matches as well as the flat default.
    """
    parts = ctx.rel.parts
    if not parts:
        return ""
    best_kind = ""
    best_len = -1
    for kind, name in ctx.config.kind_dirs.items():
        # "." (or "") means the project root: an empty prefix that still matches,
        # but loses to any more specific directory.
        wanted = () if str(name).strip() in {".", ""} else Path(name).parts
        if tuple(parts[: len(wanted)]) == wanted and len(wanted) > best_len:
            # A more specific directory wins: with study="src" and scan="src/scans",
            # a file in src/scans/ is a scan.
            best_kind = kind
            best_len = len(wanted)
    return best_kind


def check(ctx) -> list[Finding]:
    # Platform restrictions are not house style: a scan cannot call AddLabel
    # whether or not the file bothers to declare @kind. Fall back to the
    # directory when the header is absent, so `loose` on a headerless corpus
    # still catches these.
    declared = ctx.header.get("kind", "").strip().lower()
    # Only trust a kind we know; "# @kind: scna" must not disable every check.
    kind = declared if declared in ctx.config.kind_dirs else _kind_from_directory(ctx)
    if not kind:
        return []
    out: list[Finding] = []
    if kind == "scan":
        out.extend(_scan(ctx))
    elif kind == "column":
        out.extend(_column(ctx))
    elif kind == "strategy":
        out.extend(_strategy(ctx))
    return [item for item in out if item is not None]


def _calls(ctx) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for statement in ctx.statements:
        tokens = statement.tokens
        for index, token in enumerate(tokens[:-1]):
            if token.kind is not Kind.IDENT:
                continue
            if tokens[index + 1].kind is not Kind.LPAREN:
                continue
            if index > 0 and tokens[index - 1].kind is Kind.OP and tokens[index - 1].value == ".":
                continue
            found.append((token.value, token.line))
    return found


def _declares_panel(ctx) -> list[int]:
    """Lines of `declare upper/lower`, read from tokens.

    Scanning physical lines let `declare\nlower;` slip past, so a scan could
    bypass E405 with a line break.
    """
    lines: list[int] = []
    for statement in ctx.statements:
        if statement.keyword != "declare":
            continue
        words = {t.lower for t in statement.tokens if t.kind is Kind.IDENT}
        if words & {"upper", "lower"}:
            lines.append(statement.start_line)
    return lines


def _scan(ctx) -> list[Finding]:
    out: list[Finding] = []
    for name, line in _calls(ctx):
        if name.lower() in CHART_ONLY_LOWER:
            out.append(
                ctx.finding(
                    "E401",
                    line,
                    f"'{name}' is unavailable in a scan",
                    hint="Scans have no panel. Remove the drawing call.",
                )
            )
    for line in _declares_panel(ctx):
        out.append(
            ctx.finding("E405", line, "a scan has no panel; remove 'declare upper/lower'")
        )

    plots = [s for s in ctx.statements if s.keyword == "plot"]
    if len(plots) > 1:
        out.append(
            ctx.finding(
                "E406",
                plots[1].start_line,
                f"scan has {len(plots)} plots; a stock-hacker filter requires exactly one",
                hint="Schwab's scanner documentation specifies a single plot per filter.",
            )
        )

    terminated = [s for s in ctx.statements if s.tokens]
    if not terminated:
        out.append(
            ctx.finding(
                "E403",
                ctx.first_code_line or 1,
                "a scan must end with a boolean 'plot'; this scan has no statements",
            )
        )
        return [item for item in out if item is not None]
    last = terminated[-1]
    if last.keyword != "plot":
        out.append(
            ctx.finding(
                "E403",
                last.start_line,
                "a scan must end with a boolean 'plot'",
                hint="The scanner returns every symbol where that plot is true.",
            )
        )
    else:
        values = [t.value for t in last.tokens if t.kind is not Kind.SEMI]
        rhs = values[values.index("=") + 1 :] if "=" in values else []
        if len(rhs) == 1 and rhs[0].lower() in {"1", "yes", "true"}:
            out.append(
                ctx.finding(
                    "W402", last.start_line, "scan plot is a constant; every symbol matches"
                )
            )
    return [item for item in out if item is not None]


def _column(ctx) -> list[Finding]:
    out: list[Finding] = []
    for name, line in _calls(ctx):
        if name.lower() in CHART_ONLY_LOWER and name.lower() not in COLUMN_ALLOWED:
            out.append(
                ctx.finding(
                    "E402", line, f"'{name}' is unavailable in a watchlist column"
                )
            )
    for line in _declares_panel(ctx):
        out.append(
            ctx.finding(
                "E405", line, "a watchlist column has no panel; remove 'declare upper/lower'"
            )
        )
    plots = [s for s in ctx.statements if s.keyword == "plot"]
    has_label = any(name.lower() == "addlabel" for name, _line in _calls(ctx))
    if not plots and not has_label:
        # Custom quotes support label-only output, so a plot is not the only form.
        out.append(
            ctx.finding(
                "E404",
                ctx.first_code_line or 1,
                "a column needs an output: a 'plot' value or an AddLabel",
            )
        )
    elif len(plots) > 1:
        out.append(
            ctx.finding(
                "E404",
                plots[1].start_line,
                f"column has {len(plots)} plots; only the value is displayed",
            )
        )
    return [item for item in out if item is not None]


def _strategy(ctx) -> list[Finding]:
    out: list[Finding] = []
    if not any(name.lower() == "addorder" for name, _ in _calls(ctx)):
        out.append(
            ctx.finding(
                "W401",
                ctx.first_code_line or 1,
                "strategy has no AddOrder(); it will not produce a backtest",
            )
        )
    return [item for item in out if item is not None]
