"""Every capability must be documented somewhere a user will look.

A feature that exists only in the code is not shipped. This test enumerates the
real surface — argparse subcommands and flags, the MCP tool schemas, the Action's
inputs, the diagnostic codes, the ``tos.toml`` keys — and fails when one has no
documentation. It is mechanical on purpose: reviewing prose for completeness does
not scale, and the gaps are exactly the things a reviewer skims past.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def read(*parts: str) -> str:
    return (ROOT.joinpath(*parts) if parts else ROOT).read_text(encoding="utf-8")


def all_docs() -> str:
    files = [ROOT / "README.md", *(sorted(DOCS.rglob("*.md")))]
    return "\n".join(p.read_text(encoding="utf-8") for p in files if p.is_file())


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def cli_subparsers():
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from tos_toolkit.cli import _build_parser

    parser = _build_parser()
    for action in parser._actions:
        if getattr(action, "dest", None) == "command" and action.choices:
            return action.choices
    raise AssertionError("cli has no subcommands")


def test_every_command_has_a_reference_section():
    """docs/commands.md is the command reference; it must be complete."""
    commands = read("docs", "commands.md")
    missing = [
        name
        for name in cli_subparsers()
        if not re.search(rf"^## `tos {re.escape(name)}`", commands, re.MULTILINE)
    ]
    assert not missing, (
        "docs/commands.md has no section for: "
        + ", ".join(sorted(missing))
        + "\nAdd a `## `tos <name>`` heading with its flags and exit codes."
    )


def test_every_flag_is_documented():
    commands = read("docs", "commands.md")
    missing: list[str] = []
    for name, sub in cli_subparsers().items():
        for action in sub._actions:
            for option in action.option_strings:
                if not option.startswith("--") or option == "--help":
                    continue
                if option not in commands:
                    missing.append(f"tos {name} {option}")
    assert not missing, "undocumented flags:\n  " + "\n  ".join(sorted(missing))


def test_no_dead_flags():
    """A flag that is accepted but ignored is worse than an undocumented one."""
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    source = read("src", "tos_toolkit", "cli.py")

    for name, sub in cli_subparsers().items():
        handler = source.split(f'def _cmd_{name.replace("-", "_")}', 1)
        if len(handler) < 2:
            continue
        body = handler[1].split("\ndef ", 1)[0]
        for action in sub._actions:
            for option in action.option_strings:
                if not option.startswith("--") or option == "--help":
                    continue
                attr = action.dest
                # `args.<dest>` must appear in the handler that owns the flag.
                assert f"args.{attr}" in body, (
                    f"tos {name} accepts {option} but _cmd_{name} never reads "
                    f"args.{attr} — remove the flag or implement it"
                )


# --------------------------------------------------------------------------- #
# MCP
# --------------------------------------------------------------------------- #


def mcp_tools():
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from tos_toolkit import mcp

    return mcp.TOOLS


def test_every_mcp_tool_is_documented_with_its_arguments():
    agents = read("docs", "agents.md")
    missing: list[str] = []
    for tool in mcp_tools():
        name = tool["name"]
        if name not in agents:
            missing.append(f"tool {name}")
            continue
        for prop in tool["inputSchema"].get("properties", {}):
            if f"`{prop}`" not in agents:
                missing.append(f"{name} argument {prop}")
    assert not missing, "undocumented MCP surface:\n  " + "\n  ".join(missing)


def test_mcp_is_reachable_from_the_command_reference():
    """A user reading only the command reference must still find the server."""
    assert "tos mcp" in read("docs", "commands.md")


def test_mcp_is_error_contract_is_documented():
    agents = read("docs", "agents.md")
    assert "isError" in agents
    # The distinguishing claim: findings are data, not a failed call.
    assert re.search(r"isError.*(call failed|failed, not)", agents, re.DOTALL | re.IGNORECASE)


# --------------------------------------------------------------------------- #
# GitHub Action
# --------------------------------------------------------------------------- #


def action_inputs() -> list[str]:
    text = read(".github", "actions", "lint", "action.yml")
    block = text.split("inputs:", 1)[1].split("outputs:", 1)[0]
    return re.findall(r"^  ([a-z][a-z-]*):\s*$", block, re.MULTILINE)


def test_every_action_input_is_documented():
    agents = read("docs", "agents.md")
    missing = [name for name in action_inputs() if f"`{name}`" not in agents]
    assert not missing, "undocumented Action inputs:\n  " + "\n  ".join(missing)


# --------------------------------------------------------------------------- #
# Configuration and rules
# --------------------------------------------------------------------------- #


def test_every_diagnostic_code_is_in_the_rules_reference():
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from tos_toolkit.checks import DEFAULT_LEVELS

    rules = read("docs", "rules.md")
    missing = sorted(code for code in DEFAULT_LEVELS if code not in rules)
    assert not missing, "codes missing from docs/rules.md:\n  " + "\n  ".join(missing)


def test_every_toml_key_is_documented():
    configuration = read("docs", "configuration.md")
    missing: list[str] = []

    data = tomllib.loads(read("pyproject.toml"))
    assert data  # pyproject parses; the profiles below are the documented surface

    for profile in sorted((ROOT / "src" / "tos_toolkit" / "data" / "profiles").glob("*.toml")):
        parsed = tomllib.loads(profile.read_text(encoding="utf-8"))
        for section, values in parsed.items():
            for key in values:
                if f"`{key}`" not in configuration and f"{key} =" not in configuration:
                    missing.append(f"{section}.{key}")

    assert not missing, (
        "tos.toml keys not documented in docs/configuration.md:\n  "
        + "\n  ".join(sorted(set(missing)))
    )


def test_rules_reference_states_the_layer_of_every_group():
    """The layer split is the design; a rule without a layer is ambiguous."""
    rules = read("docs", "rules.md")
    assert "gated by" in rules.lower()
    assert "layer" in rules.lower()


# --------------------------------------------------------------------------- #
# Scaffolding
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "artifact",
    ["tos.toml", "justfile", ".gitignore", "AGENTS.md", "templates", "validation"],
)
def test_what_init_writes_is_documented(artifact):
    assert artifact in all_docs()
