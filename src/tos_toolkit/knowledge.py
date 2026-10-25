"""Bundled ThinkScript knowledge base.

Shipped as package data so `tos docs` works from any project, and so agents can
read the reference without finding this repo on disk.
"""

from __future__ import annotations

from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent / "docs" / "knowledge-base"

_TITLES = {
    "README": "Index and confidence markers",
    "language-reference": "Reserved words, declarations, execution model",
    "functions": "Built-in functions with signatures and confidence",
    "constants": "Enum members: Color, PriceType, AggregationPeriod, Curve, ...",
    "gotchas": "NaN, rec rules, if evaluation, fold, platform limits",
    "asset-classes": "Stock, option, future, crypto, index specifics",
    "artifact-rules": "Scan, column, strategy restrictions",
    "unverified-tokens": "Lexer-known but undocumented keywords — UNVERIFIED",
}


def topics() -> list[tuple[str, str]]:
    if not DOCS_DIR.is_dir():
        return []
    return [
        (path.stem, _TITLES.get(path.stem, path.stem))
        for path in sorted(DOCS_DIR.glob("*.md"))
    ]


def read(topic: str) -> str | None:
    path = DOCS_DIR / f"{topic}.md"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def search(needle: str) -> list[tuple[str, int, str]]:
    lowered = needle.lower()
    hits: list[tuple[str, int, str]] = []
    if not DOCS_DIR.is_dir():
        return hits
    for path in sorted(DOCS_DIR.glob("*.md")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if lowered in line.lower():
                hits.append((path.stem, line_no, line.strip()))
    return hits
