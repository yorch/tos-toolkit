"""Clean-room ThinkScript tokenizer and statement splitter.

Hand-written from the public language documentation. Nothing here is derived
from thinkorswim's own parser — see ``docs/adr/0004-no-jar-redistribution.md``.

The goal is faithful *lexing*, not parsing. Grammar validity is the job of the
optional `tos syntax-check` bridge, which calls the user's installed parser.

Key behaviours
--------------
* ``#`` starts a comment. ``//`` is **not** a comment (a common trap).
* Statements are separated by ``;``, and may span physical lines freely.
* A statement's closing ``;`` may be followed by more code on the same line.
* Bracket depth is tracked per token so callers can detect imbalance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Kind(str, Enum):
    IDENT = "ident"
    NUMBER = "number"
    STRING = "string"
    OP = "op"
    LPAREN = "lparen"
    RPAREN = "rparen"
    LBRACKET = "lbracket"
    RBRACKET = "rbracket"
    LBRACE = "lbrace"
    RBRACE = "rbrace"
    COMMA = "comma"
    SEMI = "semi"
    NEWLINE = "newline"
    UNKNOWN = "unknown"


_OPENERS = {Kind.LPAREN, Kind.LBRACKET, Kind.LBRACE}

# Statements that are a brace block with no trailing ';'.
_BLOCK_KEYWORDS = {"script", "switch", "profile"}


@dataclass(frozen=True)
class Token:
    kind: Kind
    value: str
    line: int
    col: int
    # Nesting depth *before* this token is emitted.
    depth: int = 0

    @property
    def lower(self) -> str:
        return self.value.lower()


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
_OPS = (
    "<=",
    ">=",
    "==",
    "!=",
    "&&",
    "||",
    "->",
    "+",
    "-",
    "*",
    "/",
    "%",
    "<",
    ">",
    "!",
    "=",
    "&",
    "|",
    "^",
    "~",
    "?",
    ":",
    ".",
    "@",
    "$",
)


def tokenize(text: str) -> list[Token]:
    """Turn ThinkScript source into a token list.

    Comments are dropped. Newlines are emitted so callers can reconstruct
    physical line structure if needed.
    """
    tokens: list[Token] = []
    depth = 0
    line = 1
    col = 1
    i = 0
    n = len(text)

    def emit(kind: Kind, value: str, tok_line: int, tok_col: int, tok_depth: int) -> None:
        tokens.append(Token(kind, value, tok_line, tok_col, tok_depth))

    while i < n:
        ch = text[i]

        if ch == "\n":
            emit(Kind.NEWLINE, "\n", line, col, depth)
            line += 1
            col = 1
            i += 1
            continue

        if ch in " \t\r":
            i += 1
            col += 1
            continue

        if ch == "#":
            while i < n and text[i] != "\n":
                i += 1
                col += 1
            continue

        if ch == '"':
            start_line, start_col = line, col
            buf: list[str] = []
            i += 1
            col += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    buf.append(text[i + 1])
                    i += 2
                    col += 2
                    continue
                if text[i] == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
                buf.append(text[i])
                i += 1
            if i < n:
                i += 1
                col += 1
            emit(Kind.STRING, "".join(buf), start_line, start_col, depth)
            continue

        match = _IDENT_RE.match(text, i)
        if match:
            emit(Kind.IDENT, match.group(), line, col, depth)
            col += len(match.group())
            i = match.end()
            continue

        match = _NUMBER_RE.match(text, i)
        if match:
            emit(Kind.NUMBER, match.group(), line, col, depth)
            col += len(match.group())
            i = match.end()
            continue

        if ch == "(":
            emit(Kind.LPAREN, ch, line, col, depth)
            depth += 1
            i += 1
            col += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            emit(Kind.RPAREN, ch, line, col, depth)
            i += 1
            col += 1
            continue
        if ch == "[":
            emit(Kind.LBRACKET, ch, line, col, depth)
            depth += 1
            i += 1
            col += 1
            continue
        if ch == "]":
            depth = max(0, depth - 1)
            emit(Kind.RBRACKET, ch, line, col, depth)
            i += 1
            col += 1
            continue
        if ch == "{":
            emit(Kind.LBRACE, ch, line, col, depth)
            depth += 1
            i += 1
            col += 1
            continue
        if ch == "}":
            depth = max(0, depth - 1)
            emit(Kind.RBRACE, ch, line, col, depth)
            i += 1
            col += 1
            continue
        if ch == ",":
            emit(Kind.COMMA, ch, line, col, depth)
            i += 1
            col += 1
            continue
        if ch == ";":
            emit(Kind.SEMI, ch, line, col, depth)
            i += 1
            col += 1
            continue

        for op in _OPS:
            if text.startswith(op, i):
                emit(Kind.OP, op, line, col, depth)
                i += len(op)
                col += len(op)
                break
        else:
            emit(Kind.UNKNOWN, ch, line, col, depth)
            i += 1
            col += 1

    return tokens


@dataclass
class Statement:
    """One ``;``-terminated statement (or a trailing unterminated one)."""

    tokens: list[Token]
    start_line: int
    terminated: bool

    @property
    def first(self) -> Token | None:
        return self.tokens[0] if self.tokens else None

    @property
    def keyword(self) -> str:
        """Lowercased leading identifier, if the statement starts with one."""
        token = self.first
        return token.lower if token is not None and token.kind is Kind.IDENT else ""

    @property
    def text(self) -> str:
        return " ".join(t.value for t in self.tokens)


def split_statements(tokens: list[Token]) -> list[Statement]:
    """Split a flat token stream into statements on top-level ``;``."""
    statements: list[Statement] = []
    current: list[Token] = []

    for token in tokens:
        if token.kind is Kind.NEWLINE:
            continue
        if token.kind is Kind.SEMI and token.depth == 0:
            statements.append(
                Statement(current, current[0].line if current else token.line, True)
            )
            current = []
            continue
        current.append(token)
        # A `script NAME { ... }` block is a statement with no trailing ';'.
        # Without this, the next declaration is glued onto the block and every
        # later check sees one statement whose keyword is 'script'.
        #
        # Restricted to block-introducing keywords so `if c { } else { }` style
        # chains are not split into a stray `else` statement.
        if token.kind is Kind.RBRACE and token.depth == 0 and current:
            head = current[0]
            if head.kind is Kind.IDENT and head.lower in _BLOCK_KEYWORDS:
                statements.append(Statement(current, head.line, True))
                current = []

    if current:
        statements.append(Statement(current, current[0].line, False))
    return statements


def strip_comments_and_strings(text: str) -> str:
    """Blank out comments and string bodies, preserving line/column layout.

    Useful for regex-style checks that should not match inside literals.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            if ch == "\\" and i + 1 < n:
                out.append("  ")
                i += 2
                continue
            if ch == '"':
                in_string = False
            out.append(" ")
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(" ")
            i += 1
            continue
        if ch == "#":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def find_calls(statements: list[Statement]) -> list[Token]:
    """Identifiers used as function calls: ``name(`` not preceded by ``.``."""
    calls: list[Token] = []
    for statement in statements:
        tokens = statement.tokens
        for idx, token in enumerate(tokens[:-1]):
            if token.kind is not Kind.IDENT:
                continue
            if tokens[idx + 1].kind is not Kind.LPAREN:
                continue
            if idx > 0 and tokens[idx - 1].kind is Kind.OP and tokens[idx - 1].value == ".":
                continue
            calls.append(token)
    return calls
