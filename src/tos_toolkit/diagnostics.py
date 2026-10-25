"""Diagnostics: findings, reports, exit codes.

Every rule emits a `Finding` with a stable code. Codes are API: ``E071`` means
one thing forever. Add new codes, never repurpose an old one.

Code ranges
-----------
``E001``-``E006``  lexical / file hygiene (tabs, newlines, ``//``, delimiters)
``E031``          declaration placement
``E050``          asset class declarations
``E070``-``E073``  identifiers (duplicates, collisions, unknown functions)
``E101``-``W104``  header block and input documentation (profile-gated)
``E120``          artifact kind vs location (profile-gated)
``E401``-``W402``  artifact restrictions (scans, columns, strategies)
``W001``, ``W002``  style
``W050``          repaint honesty
``W080``, ``W081``  naming (profile-gated)
``W090``, ``W091``  unverified ``rec`` behaviour

See ``docs/rules.md`` for the authoritative list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclass(frozen=True)
class Finding:
    """A single diagnostic."""

    path: str
    line: int
    code: str
    message: str
    severity: str = ERROR
    hint: str | None = None

    @property
    def is_error(self) -> bool:
        return self.severity == ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity == WARNING

    def render(self, relative_to: Path | None = None) -> str:
        path = self.path
        if relative_to is not None:
            try:
                path = str(Path(self.path).relative_to(relative_to))
            except ValueError:
                pass
        loc = f"{path}:{self.line}" if self.line else path
        out = f"{loc}: [{self.code}] {self.message}"
        if self.hint:
            out += f"\n    hint: {self.hint}"
        return out


@dataclass
class Report:
    """Accumulates findings for one run."""

    findings: list[Finding] = field(default_factory=list)
    files_checked: int = 0

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def extend(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.is_error]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.is_warning]

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings, key=lambda f: (f.path, f.line or 0, f.code))

    def summary(self) -> str:
        return (
            f"{self.files_checked} file(s) checked · "
            f"{len(self.errors)} error(s) · {len(self.warnings)} warning(s)"
        )


class Level(str, Enum):
    """Configurable severity for a rule."""

    OFF = "off"
    WARN = "warn"
    ERROR = "error"

    def severity(self) -> str | None:
        if self is Level.OFF:
            return None
        return ERROR if self is Level.ERROR else WARNING
