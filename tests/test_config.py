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


def test_missing_explicit_config_raises(tmp_path):
    with pytest.raises(ConfigError, match="config not found"):
        load(config_path=tmp_path / "nope.toml")


def test_malformed_toml_raises(tmp_path):
    path = tmp_path / "tos.toml"
    path.write_text("this is not toml [[[", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load(config_path=path)


def test_review_defaults_are_the_pinned_gate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = load()
    assert config.review_harness == "codex"
    assert config.review_model == "gpt-6.1-sol"


def test_local_template_wins_over_packaged(tmp_path, monkeypatch):
    from tos_toolkit.scaffold import new_file
    from tos_toolkit.config import load as load_config

    (tmp_path / "tos.toml").write_text(
        '[project]\ntemplates_dir = "templates"\n', encoding="utf-8"
    )
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "study.thinkscript").write_text(
        "# @name: __NAME__\n# LOCAL TEMPLATE\ndeclare upper;\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    config = load_config()
    new_file(config, "study", "trend/from_local", None)
    body = (tmp_path / "studies" / "trend" / "from_local.thinkscript").read_text()
    assert "LOCAL TEMPLATE" in body


def test_kind_dirs_merges_rather_than_replaces(tmp_path, monkeypatch):
    (tmp_path / "tos.toml").write_text(
        '[project]\nkind_dirs = { study = "indicators" }\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    config = load()
    assert config.kind_dirs["study"] == "indicators"
    # the rest must survive
    assert config.kind_dirs["scan"] == "scans"
    assert config.kind_dirs["column"] == "columns"


def test_version_matches_pyproject():
    """A version string that drifts from pyproject is a packaging bug.

    0.2.0 shipped reporting 0.1.0 because __version__ was maintained by hand; it
    now comes from installed metadata, and this guards the relationship.
    """
    import tomllib
    from pathlib import Path

    import tos_toolkit

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    # An installed distribution reports its metadata version, which equals the
    # declared one; a bare source checkout reports 0.0.0+source.
    if tos_toolkit.__version__ == "0.0.0+source":
        pytest.skip("running from an uninstalled source checkout")
    assert tos_toolkit.__version__ == declared
