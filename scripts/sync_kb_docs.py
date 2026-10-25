#!/usr/bin/env python3
"""Copy the packaged ThinkScript reference into the docs tree for site builds.

The knowledge base has exactly one source of truth: it ships inside the package
so that `tos docs` works from any project. MkDocs can only see files under
`docs/`, so this script stages a copy. `docs/knowledge-base/` is gitignored —
never edit the staged copy.

Used by `just docs-build` and the Pages workflow.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "tos_toolkit" / "docs" / "knowledge-base"
TARGET = ROOT / "docs" / "knowledge-base"


def main() -> int:
    if not SOURCE.is_dir():
        print(f"error: knowledge base not found at {SOURCE}", file=sys.stderr)
        return 2

    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)

    files = sorted(path.name for path in TARGET.glob("*.md"))
    print(f"staged {len(files)} knowledge-base file(s) into {TARGET.relative_to(ROOT)}")
    for name in files:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
