"""Function and constant registry.

Curated by hand from the public ThinkScript reference and from observed
behaviour. Entries carry a confidence level because inventing a function is the
single most common ThinkScript mistake — the registry exists to catch it.

Confidence values
-----------------
``verified``   used in a script that rendered in the platform
``documented`` present in the official reference
``unverified`` believed real, never tested — do not ship on this alone

The registry is data, not law: ``unknown_functions`` defaults to ``warn``, and
any project can turn it off. It will always lag the platform.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class FunctionInfo:
    name: str
    category: str
    confidence: str
    notes: str = ""

    @property
    def is_unverified(self) -> bool:
        return self.confidence == "unverified"


class Registry:
    """Case-insensitive lookup over known function and constant names."""

    def __init__(self, functions: list[FunctionInfo], constants: dict[str, list[str]]):
        self._functions = {f.name.lower(): f for f in functions}
        self._constants = {k: list(v) for k, v in constants.items()}
        # Keyed and valued in lowercase: lookups are always case-insensitive.
        self._constant_lower = {
            k.lower(): {v.lower() for v in values} for k, values in self._constants.items()
        }

    def function(self, name: str) -> FunctionInfo | None:
        return self._functions.get(name.lower())

    def has_function(self, name: str) -> bool:
        return name.lower() in self._functions

    def namespace_members(self, namespace: str) -> set[str]:
        return self._constant_lower.get(namespace.lower(), set())

    def namespace_names(self) -> list[str]:
        return [name for name in self._constants]

    def has_namespace(self, namespace: str) -> bool:
        return namespace.lower() in self._constant_lower

    def namespaces(self) -> list[str]:
        return sorted(self._constants)

    def all_functions(self) -> list[FunctionInfo]:
        return sorted(self._functions.values(), key=lambda f: f.name.lower())


@lru_cache(maxsize=1)
def load() -> Registry:
    functions = [
        FunctionInfo(
            name=entry["name"],
            category=entry.get("category", "other"),
            confidence=entry.get("confidence", "documented"),
            notes=entry.get("notes", ""),
        )
        for entry in json.loads((DATA_DIR / "functions.json").read_text(encoding="utf-8"))[
            "functions"
        ]
    ]
    constants = json.loads((DATA_DIR / "constants.json").read_text(encoding="utf-8"))[
        "constants"
    ]
    return Registry(functions, constants)
