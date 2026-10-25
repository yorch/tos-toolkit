"""Test helpers."""

from __future__ import annotations

from pathlib import Path

from tos_toolkit.checks import Context
from tos_toolkit.config import Config
from tos_toolkit.registry import load as load_registry


def make_ctx(
    tmp_path: Path,
    text: str,
    *,
    profile: str = "strict",
    subdir: str = "studies/trend",
    filename: str = "sample.thinkscript",
    **overrides,
) -> Context:
    """Build a Context for a synthetic file inside *subdir*."""
    config = Config(root=tmp_path, profile=profile)
    if profile == "loose":
        config.header_mode = "off"
        config.targets = []
    for key, value in overrides.items():
        setattr(config, key, value)

    path = tmp_path / subdir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return Context(
        path=path,
        root=tmp_path,
        text=text,
        config=config,
        registry=load_registry(),
    )


def codes(findings) -> set[str]:
    return {f.code for f in findings if f is not None}
