"""Language-generic rules.

Everything here is true of ThinkScript anywhere, on any chart, in any repo. No
rule in this module may depend on house conventions — those belong in `header`,
`artifacts`, or `layout`.
"""

from __future__ import annotations

import re

from ..diagnostics import Finding
from ..lexer import Kind

MAX_COLUMNS = 100

# Functions that draw on a chart panel and are therefore unavailable in scans.
CHART_ONLY = {
    "AddCloud",
    "AddChartBubble",
    "AddLabel",
    "AddVerticalLine",
    "AssignBackgroundColor",
    "AssignPriceColor",
}

_RESERVED = {
    "and",
    "declare",
    "def",
    "else",
    "fold",
    "if",
    "input",
    "no",
    "not",
    "or",
    "plot",
    "rec",
    "script",
    "then",
    "yes",
}


def check(ctx) -> list[Finding]:
    out: list[Finding] = []
    for fn in (
        _tabs,
        _trailing_newline,
        _double_slash,
        _delimiters,
        _duplicate_identifiers,
        _case_collisions,
        _recursion,
        _unknown_functions,
        _reserved_assignment,
        _style,
    ):
        out.extend(item for item in fn(ctx) if item is not None)
    return out


def _tabs(ctx) -> list[Finding]:
    out = []
    for lineno, line in enumerate(ctx.text.splitlines(), start=1):
        if "\t" in line:
            out.append(
                ctx.finding(
                    "E001",
                    lineno,
                    "tab character; ThinkScript sources use 4 spaces",
                    hint="Most editors can convert on save.",
                )
            )
            break
    return out


def _trailing_newline(ctx) -> list[Finding]:
    if ctx.text and not ctx.text.endswith("\n"):
        return [ctx.finding("E002", 0, "missing trailing newline")]
    return []


def _double_slash(ctx) -> list[Finding]:
    out = []
    for lineno, line in enumerate(ctx.masked_lines(), start=1):
        if "//" in line:
            out.append(
                ctx.finding(
                    "E003",
                    lineno,
                    "'//' is not a comment in ThinkScript; use '#'",
                    hint="'//' parses as two division operators.",
                )
            )
    return out


def _delimiters(ctx) -> list[Finding]:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[tuple[str, int]] = []
    out: list[Finding] = []
    for token in ctx.tokens:
        if token.kind in {Kind.LPAREN, Kind.LBRACKET, Kind.LBRACE}:
            stack.append((token.value, token.line))
        elif token.kind in {Kind.RPAREN, Kind.RBRACKET, Kind.RBRACE}:
            if not stack or stack[-1][0] != pairs[token.value]:
                out.append(
                    ctx.finding("E004", token.line, f"unmatched '{token.value}'")
                )
                stack.clear()
                continue
            stack.pop()
    for opener, line in stack:
        out.append(ctx.finding("E004", line, f"unclosed '{opener}'"))
    return out


def _duplicate_identifiers(ctx) -> list[Finding]:
    seen: dict[str, int] = {}
    out: list[Finding] = []
    for statement in ctx.statements:
        if statement.keyword not in {"def", "rec", "plot", "input"}:
            continue
        name = next(
            (t for t in statement.tokens[1:] if t.kind is Kind.IDENT), None
        )
        if name is None:
            continue
        key = name.lower
        out.append(
            ctx.finding(
                "E070", name.line, f"identifier '{name.value}' declared more than once"
            )
            if key in seen
            else None
        )
        seen.setdefault(key, name.line)
    return [item for item in out if item is not None]


def _case_collisions(ctx) -> list[Finding]:
    """ThinkScript identifiers are case-insensitive; def and plot must not collide."""
    defs: dict[str, str] = {}
    plots: dict[str, str] = {}
    for statement in ctx.statements:
        keyword = statement.keyword
        if keyword not in {"def", "rec", "input", "plot"}:
            continue
        name = next((t for t in statement.tokens[1:] if t.kind is Kind.IDENT), None)
        if name is None:
            continue
        if keyword == "plot":
            plots.setdefault(name.lower, name.value)
        else:
            defs.setdefault(name.lower, name.value)
    out = []
    for key in sorted(set(defs) & set(plots)):
        out.append(
            ctx.finding(
                "E071",
                ctx.header_lines.get("name", 1),
                f"'{defs[key]}' and '{plots[key]}' are the same identifier "
                "(ThinkScript is case-insensitive)",
                hint="Rename one of them; this fails to compile as 'Identifier Already Used'.",
            )
        )
    return out


def _recursion(ctx) -> list[Finding]:
    from ..lexer import Statement  # local import keeps module import order simple

    out: list[Finding] = []
    for statement in ctx.statements:
        if statement.keyword != "rec":
            continue
        tokens = statement.tokens
        name = next((t for t in tokens[1:] if t.kind is Kind.IDENT), None)
        if name is None:
            continue
        key = name.lower
        uses = sum(1 for t in tokens if t.kind is Kind.IDENT and t.lower == key)
        if uses > 1:
            out.append(
                ctx.finding(
                    "W090",
                    name.line,
                    f"recursive variable '{name.value}' references itself {uses}x; "
                    "the platform's exact rule is unverified",
                    hint="One self-reference per branch is believed safe; test before shipping.",
                )
            )
        for index, token in enumerate(tokens):
            if (
                token.kind is Kind.LBRACKET
                and index + 1 < len(tokens)
                and tokens[index + 1].kind is Kind.NUMBER
                and tokens[index - 1].kind is Kind.IDENT
                and tokens[index - 1].lower == key
            ):
                try:
                    depth = int(tokens[index + 1].value)
                except ValueError:
                    continue
                if depth > 1:
                    out.append(
                        ctx.finding(
                            "W091",
                            token.line,
                            f"recursive variable '{name.value}' self-references at "
                            f"[{depth}]; only [1] is expected to be supported",
                        )
                    )
    return [item for item in out if item is not None]


def _unknown_functions(ctx) -> list[Finding]:
    """Report calls to names that are neither built-ins nor declared locally."""
    declared = set(ctx.declared_identifiers())
    scripts = ctx.script_names()
    out: list[Finding] = []
    reported: set[str] = set()
    for statement in ctx.statements:
        tokens = statement.tokens
        for index, token in enumerate(tokens[:-1]):
            if token.kind is not Kind.IDENT:
                continue
            if tokens[index + 1].kind is not Kind.LPAREN:
                continue
            if index > 0 and tokens[index - 1].kind is Kind.OP and tokens[index - 1].value == ".":
                continue
            key = token.lower
            if key in _RESERVED or key in declared or key in scripts or key in reported:
                continue
            if ctx.registry.has_function(key):
                continue
            reported.add(key)
            out.append(
                ctx.finding(
                    "E072",
                    token.line,
                    f"unknown function '{token.value}'",
                    hint="Not in the registry. Verify in the platform before shipping.",
                    setting="unknown_functions",
                )
            )
    return [item for item in out if item is not None]


def _reserved_assignment(ctx) -> list[Finding]:
    out = []
    for statement in ctx.statements:
        if statement.keyword in {"def", "rec", "plot", "input"}:
            continue
        tokens = statement.tokens
        if (
            len(tokens) >= 2
            and tokens[0].kind is Kind.IDENT
            and tokens[1].kind is Kind.OP
            and tokens[1].value == "="
        ):
            if not any(t.kind is Kind.IDENT and t.lower in {"if"} for t in tokens):
                out.append(
                    ctx.finding(
                        "E073",
                        tokens[0].line,
                        f"'{tokens[0].value}' assigned without def/rec/plot/input",
                        hint="ThinkScript has no bare assignment; use 'def' or 'rec'.",
                    )
                )
    return [item for item in out if item is not None]


def _style(ctx) -> list[Finding]:
    out: list[Finding] = []
    in_header = True
    for lineno, line in enumerate(ctx.text.splitlines(), start=1):
        if line != line.rstrip():
            out.append(ctx.finding("W001", lineno, "trailing whitespace"))
        header_line = in_header and line.lstrip().startswith("# @")
        if len(line) > MAX_COLUMNS and not header_line:
            out.append(
                ctx.finding(
                    "W002", lineno, f"line is {len(line)} chars (max {MAX_COLUMNS})"
                )
            )
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            in_header = False
    return [item for item in out if item is not None]
