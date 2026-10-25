"""Configuration and profile resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from tos_toolkit.config import Config, ConfigError, discover, load
from tos_toolkit.diagnostics import Level


def test_defaults_to_strict_with_no_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = load()
    assert config.profile == "strict"
    assert config.header_mode == "required"


def test_loose_profile_disables_header(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = load(profile="loose")
    assert config.header_mode == "off"
    assert config.targets == []


def test_unknown_profile_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError, match="unknown profile"):
        load(profile="nope")


def test_tos_toml_overrides_profile(tmp_path, monkeypatch):
    (tmp_path / "tos.toml").write_text(
        '[profile]\nname = "loose"\n\n[checks]\nunknown_functions = "error"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    config = load()
    assert config.profile == "loose"
    assert config.header_mode == "off"
    assert config.rules["unknown_functions"] is Level.ERROR


def test_discover_walks_upwards(tmp_path, monkeypatch):
    (tmp_path / "tos.toml").write_text("[profile]\nname = 'strict'\n", encoding="utf-8")
    nested = tmp_path / "studies" / "trend"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    found = discover(nested)
    assert found == tmp_path / "tos.toml"


def test_invalid_rule_level_raises(tmp_path, monkeypatch):
    (tmp_path / "tos.toml").write_text('[checks]\nE071 = "nope"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError, match="invalid"):
        load()


def test_parser_path_configurable(tmp_path, monkeypatch):
    (tmp_path / "tos.toml").write_text(
        '[parser]\nenabled = false\ntos_path = "/opt/tos"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    config = load()
    assert config.parser_enabled is False
    assert config.tos_path == "/opt/tos"


def test_level_lookup_prefers_exact_code():
    config = Config(root=Path("/tmp"), rules={"E072": Level.OFF})
    assert config.level("E072") is Level.OFF
