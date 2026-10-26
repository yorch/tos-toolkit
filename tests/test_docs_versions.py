"""Documentation must not pin a stale release.

Every install example names a version, and every release invalidates it. Rather
than trust a reviewer to notice, this reads the version from ``pyproject.toml`` and
fails when a doc pins a different one. It is the same class of bug as a stale
``__version__``: harmless-looking, and wrong in the one place a new user looks
first.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# `tos-toolkit==0.2.1` in a shell block, `actions/lint@v0.2.1` in a workflow, or
# `version: "0.2.1"` in an action input.
PIN_PATTERNS = [
    re.compile(r"tos-toolkit==(\d+\.\d+\.\d+)"),
    re.compile(r"tos-toolkit@v(\d+\.\d+\.\d+)"),
    re.compile(r"actions/lint@v(\d+\.\d+\.\d+)"),
    re.compile(r'version:\s*"(\d+\.\d+\.\d+)"'),
]


def current_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def doc_files() -> list[Path]:
    files = [ROOT / "README.md"]
    files.extend(sorted((ROOT / "docs").rglob("*.md")))
    return [f for f in files if f.is_file()]


def find_pins(text: str) -> list[tuple[int, str, str]]:
    hits: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in PIN_PATTERNS:
            for match in pattern.finditer(line):
                hits.append((lineno, match.group(0), match.group(1)))
    return hits


def test_every_pinned_version_matches_pyproject():
    expected = current_version()
    problems: list[str] = []

    for path in doc_files():
        for lineno, snippet, pinned in find_pins(path.read_text(encoding="utf-8")):
            if pinned != expected:
                rel = path.relative_to(ROOT)
                problems.append(
                    f"{rel}:{lineno} pins {pinned} but pyproject.toml says {expected}  ({snippet})"
                )

    assert not problems, (
        "Documentation pins a stale release:\n  "
        + "\n  ".join(problems)
        + "\nUpdate the install examples, or bump pyproject.toml."
    )


def test_readme_documents_the_real_install_command():
    """`pip install -e .` inside a consumer repo installs nothing useful."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install_section = readme.split("## Install", 1)[-1].split("---", 1)[0]
    assert "pipx install tos-toolkit" in install_section
    assert "pip install tos-toolkit" in install_section
    assert "pip install -e ." not in install_section


@pytest.mark.parametrize("name", ["consuming.md", "publishing.md", "agents.md"])
def test_guides_use_pypi_first(name):
    """The PyPI install is the documented default; git is the fallback."""
    body = (ROOT / "docs" / name).read_text(encoding="utf-8")
    assert "pipx install tos-toolkit" in body or "pip install tos-toolkit" in body
