"""Check orchestration.

A `Context` carries everything a rule needs about one file. Rules live in four
modules and are split by *layer*:

``language``  true of ThinkScript anywhere — always on
``header``    the ``# @key:`` block — profile-gated
``artifacts`` platform rules for scans/columns/strategies — always on
``layout``    kind-vs-directory and naming — fires only inside a kind directory
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from ..diagnostics import ERROR, WARNING, Finding, Level
from ..lexer import Statement, Token, split_statements, strip_comments_and_strings, tokenize
from ..registry import Registry

# Default severity per code. A rule set to `off` never fires; `warn` downgrades;
# `error` upgrades.
DEFAULT_LEVELS: dict[str, Level] = {
    "E001": Level.ERROR,
    "E002": Level.ERROR,
    "E003": Level.ERROR,
    "E004": Level.ERROR,
    "E005": Level.ERROR,
    "E006": Level.ERROR,
    "E070": Level.ERROR,
    "E071": Level.ERROR,
    "E072": Level.WARN,
    "E073": Level.WARN,
    "E101": Level.ERROR,
    "E102": Level.ERROR,
    "E103": Level.ERROR,
    "E104": Level.ERROR,
    "E120": Level.ERROR,
    "E031": Level.WARN,
    "E050": Level.ERROR,
    "E401": Level.ERROR,
    "E402": Level.ERROR,
    "E403": Level.ERROR,
    "E404": Level.ERROR,
    "E405": Level.ERROR,
    "W001": Level.WARN,
    "W002": Level.WARN,
    "W050": Level.WARN,
    "W101": Level.WARN,
    "W102": Level.WARN,
    "W103": Level.WARN,
    "W104": Level.WARN,
    "W401": Level.WARN,
    "W402": Level.WARN,
    "W080": Level.WARN,
    "W081": Level.WARN,
    "W090": Level.WARN,
    "W091": Level.WARN,
}


@dataclass
class Context:
    path: Path
    root: Path
    text: str
    config: Config
    registry: Registry

    def __post_init__(self) -> None:
        self.tokens: list[Token] = tokenize(self.text)
        self.statements: list[Statement] = split_statements(self.tokens)
        self.code: str = strip_comments_and_strings(self.text)
        self.header: dict[str, str] = {}
        self.header_lines: dict[str, int] = {}
        self.first_code_line: int | None = None
        self._parse_header()
        try:
            self.rel = self.path.resolve().relative_to(self.root.resolve())
        except ValueError:
            self.rel = self.path

    # -- header ---------------------------------------------------------
    def _parse_header(self) -> None:
        for index, raw in enumerate(self.text.splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            if not line.startswith("#"):
                self.first_code_line = index
                return
            match = re.match(r"^#\s*@([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
            if match:
                key = match.group(1).lower()
                if key not in self.header:
                    self.header[key] = match.group(2).strip()
                    self.header_lines[key] = index

    # -- reporting ------------------------------------------------------
    @property
    def rel_posix(self) -> str:
        return self.rel.as_posix()

    def level(self, code: str, setting: str | None = None) -> Level:
        if code in self.config.rules:
            return self.config.rules[code]
        if setting and setting in self.config.rules:
            return self.config.rules[setting]
        return DEFAULT_LEVELS.get(code, Level.ERROR)

    def finding(
        self,
        code: str,
        line: int,
        message: str,
        hint: str | None = None,
        setting: str | None = None,
    ) -> Finding | None:
        """Build a Finding honouring the configured level, or None if disabled."""
        level = self.level(code, setting)
        if level is Level.OFF:
            return None
        severity = ERROR if level is Level.ERROR else WARNING
        return Finding(self.rel_posix, line, code, message, severity, hint)

    # -- helpers --------------------------------------------------------
    def masked_lines(self) -> list[str]:
        return self.code.splitlines()

    def declared_identifiers(self) -> dict[str, str]:
        """Map lowercased identifier -> declaring keyword."""
        declared: dict[str, str] = {}
        for statement in self.statements:
            keyword = statement.keyword
            if keyword not in {"def", "rec", "plot", "input"}:
                continue
            for token in statement.tokens[1:]:
                if token.kind.name == "IDENT":
                    declared.setdefault(token.lower, keyword)
                    break
        return declared

    def script_names(self) -> set[str]:
        """Names defined by `script` blocks, which are callable."""
        names: set[str] = set()
        tokens = self.tokens
        for index, token in enumerate(tokens):
            if token.kind.name == "IDENT" and token.lower == "script":
                for follower in tokens[index + 1 :]:
                    if follower.kind.name == "IDENT":
                        names.add(follower.lower)
                        break
                    if follower.kind.name == "LBRACE":
                        break
        return names


def run_all(ctx: Context) -> list[Finding]:
    """Run every applicable rule against one file."""
    from . import artifacts, header, language, layout

    findings: list[Finding] = []
    for module in (language, header, artifacts, layout):
        findings.extend(module.check(ctx))
    return [f for f in findings if f is not None]
