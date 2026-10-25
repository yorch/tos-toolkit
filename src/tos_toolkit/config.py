"""Configuration: ``tos.toml`` discovery and profile resolution.

Two layers, resolved in this order (later wins):

1. Built-in profile from ``data/profiles/<name>.toml`` (``strict`` or ``loose``).
2. The project's own ``tos.toml``.

Any rule can be set to ``off`` / ``warn`` / ``error`` in ``[checks]``.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .diagnostics import Level

CONFIG_NAME = "tos.toml"
DATA_DIR = Path(__file__).resolve().parent / "data"
PROFILE_DIR = DATA_DIR / "profiles"

KIND_DIRS_DEFAULT = {
    "study": "studies",
    "scan": "scans",
    "strategy": "strategies",
    "column": "columns",
}
KINDS = set(KIND_DIRS_DEFAULT)
STATUSES = {"draft", "validated", "in-use", "deprecated"}
PANELS = {"upper", "lower", "none"}
ASSETS = {"stock", "option", "future", "crypto", "index"}
TIMEFRAMES = {"intraday", "daily", "weekly", "monthly"}

REQUIRED_HEADER_KEYS = [
    "name",
    "kind",
    "panel",
    "assets",
    "timeframes",
    "version",
    "status",
]
OPTIONAL_HEADER_KEYS = [
    "inputs",
    "repaints",
    "notes",
    "superseded-by",
    "requires",
]


class ConfigError(Exception):
    """Raised when configuration is unusable."""


@dataclass
class Config:
    root: Path
    profile: str = "strict"
    # project
    targets: list[str] = field(
        default_factory=lambda: ["studies", "scans", "strategies", "columns"]
    )
    kind_dirs: dict[str, str] = field(default_factory=lambda: dict(KIND_DIRS_DEFAULT))
    templates_dir: str = "templates"
    # header
    header_mode: str = "required"  # required | optional | off
    required_keys: list[str] = field(default_factory=lambda: list(REQUIRED_HEADER_KEYS))
    optional_keys: list[str] = field(default_factory=lambda: list(OPTIONAL_HEADER_KEYS))
    statuses: set[str] = field(default_factory=lambda: set(STATUSES))
    assets: set[str] = field(default_factory=lambda: set(ASSETS))
    timeframes: set[str] = field(default_factory=lambda: set(TIMEFRAMES))
    panels: set[str] = field(default_factory=lambda: set(PANELS))
    # checks: code -> Level
    rules: dict[str, Level] = field(default_factory=dict)
    # parser bridge
    parser_enabled: bool = True
    tos_path: str = "/Applications/thinkorswim"
    # review
    review_harness: str = "claude"
    review_model: str = "claude-opus-5-5"
    review_effort: str = "high"

    def level(self, code: str, default: Level = Level.ERROR) -> Level:
        return self.rules.get(code, default)


def load_profile(name: str) -> dict:
    path = PROFILE_DIR / f"{name}.toml"
    if not path.is_file():
        available = sorted(p.stem for p in PROFILE_DIR.glob("*.toml"))
        raise ConfigError(
            f"unknown profile '{name}' (available: {', '.join(available) or 'none'})"
        )
    with path.open("rb") as handle:
        return tomllib.load(handle)


def discover(start: Path | None = None) -> Path | None:
    """Walk up from *start* looking for ``tos.toml``."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        path = candidate / CONFIG_NAME
        if path.is_file():
            return path
    return None


def _merge_rules(target: dict[str, Level], table: dict) -> None:
    for code, value in table.items():
        if not isinstance(value, str):
            raise ConfigError(f"[checks] {code} must be a string, got {type(value).__name__}")
        try:
            target[code] = Level(value.lower())
        except ValueError:
            raise ConfigError(
                f"[checks] {code} = '{value}' is invalid (use off | warn | error)"
            ) from None


def load(config_path: Path | None = None, profile: str | None = None) -> Config:
    """Resolve configuration. Falls back to the `strict` profile with no file."""
    path = config_path or discover()
    data: dict = {}
    root = Path.cwd()

    if path is not None:
        if not path.is_file():
            raise ConfigError(f"config not found: {path}")
        root = path.parent
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"invalid TOML in {path}: {exc}") from exc

    profile_name = profile or data.get("profile", {}).get("name", "strict")
    profile_data = load_profile(profile_name)

    config = Config(root=root, profile=profile_name)

    for section in (profile_data, data):
        project = section.get("project", {})
        if "targets" in project:
            config.targets = list(project["targets"])
        if "kind_dirs" in project:
            config.kind_dirs = {str(k): str(v) for k, v in project["kind_dirs"].items()}
        if "templates_dir" in project:
            config.templates_dir = str(project["templates_dir"])

        header = section.get("header", {})
        if "mode" in header:
            mode = str(header["mode"]).lower()
            if mode not in {"required", "optional", "off"}:
                raise ConfigError(f"[header] mode = '{mode}' invalid (required|optional|off)")
            config.header_mode = mode
        if "required" in header:
            config.required_keys = list(header["required"])
        if "optional" in header:
            config.optional_keys = list(header["optional"])
        if "statuses" in header:
            config.statuses = set(header["statuses"])
        if "assets" in header:
            config.assets = set(header["assets"])
        if "timeframes" in header:
            config.timeframes = set(header["timeframes"])
        if "panels" in header:
            config.panels = set(header["panels"])

        parser = section.get("parser", {})
        if "enabled" in parser:
            config.parser_enabled = bool(parser["enabled"])
        if "tos_path" in parser:
            config.tos_path = str(parser["tos_path"])

        review = section.get("review", {})
        if "harness" in review:
            config.review_harness = str(review["harness"])
        if "model" in review:
            config.review_model = str(review["model"])
        if "effort" in review:
            config.review_effort = str(review["effort"])

        _merge_rules(config.rules, section.get("checks", {}))

    unknown_kinds = set(config.kind_dirs) - KINDS
    if unknown_kinds:
        raise ConfigError(f"[project] unknown artifact kind(s): {', '.join(sorted(unknown_kinds))}")

    return config
