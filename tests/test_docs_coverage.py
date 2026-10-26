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


def command_sections() -> dict[str, str]:
    """Split docs/commands.md into one blob per `## `tos <name>`` section."""
    commands = read("docs", "commands.md")
    sections: dict[str, str] = {}
    current = None
    buffer: list[str] = []
    for line in commands.splitlines():
        match = re.match(r"^## `tos ([a-z-]+)`", line)
        if match:
            if current:
                sections[current] = "\n".join(buffer)
            current = match.group(1)
            buffer = []
            continue
        if current and line.startswith("## "):
            sections[current] = "\n".join(buffer)
            current = None
            buffer = []
            continue
        if current:
            buffer.append(line)
    if current:
        sections[current] = "\n".join(buffer)
    return sections


def test_every_flag_is_documented_in_its_own_section():
    """A flag mentioned anywhere is not documented: it must be in its command's section.

    Matching the whole file let `init --profile` pass on the strength of the global
    usage line.
    """
    sections = command_sections()
    missing: list[str] = []
    for name, sub in cli_subparsers().items():
        section = sections.get(name, "")
        for action in sub._actions:
            for option in action.option_strings:
                if not option.startswith("--") or option == "--help":
                    continue
                if option not in section:
                    missing.append(f"tos {name} {option} is not in the `tos {name}` section")
    assert not missing, "undocumented flags:\n  " + "\n  ".join(sorted(missing))


def test_no_dead_flags():
    """A flag that is accepted but ignored is worse than an undocumented one."""
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    source = read("src", "tos_toolkit", "cli.py")

    for name, sub in cli_subparsers().items():
        # The handler name does not always mirror the command name (syntax-check
        # is `_cmd_syntax`). Resolve it through the COMMANDS table, and fail loudly
        # when it cannot be found — silently skipping is how a dead flag hid here.
        registered = re.search(rf'"{re.escape(name)}":\s*(_cmd_[a-z_]+)', source)
        assert registered, f"no COMMANDS entry found for '{name}'"
        handler = source.split(f"def {registered.group(1)}", 1)
        assert len(handler) == 2, f"handler {registered.group(1)} not found in cli.py"
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


def test_every_command_states_its_exit_codes():
    """Every command can fail; a reference that hides its exit codes cannot gate CI.

    Accepts a table row or a sentence, but the section must name an actual numeric
    exit code — not merely contain the word.
    """
    sections = command_sections()
    missing = []
    for name, body in sections.items():
        stated = [
            line
            for line in body.splitlines()
            if re.search(r"exit", line, re.IGNORECASE) and re.search(r"\b[0-9]\b", line)
        ]
        if not stated:
            missing.append(name)
    assert not missing, (
        "these command sections never state a numeric exit code: "
        + ", ".join(sorted(missing))
    )


# --------------------------------------------------------------------------- #
# MCP
# --------------------------------------------------------------------------- #


def mcp_tools():
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from tos_toolkit import mcp

    return mcp.TOOLS


def mcp_table_rows() -> dict[str, str]:
    """The MCP tool table on the Agents page, one row per tool.

    Checking the whole file let `paths`, `profile` and `strict` pass because the
    GitHub Action's inputs table also contains them. The arguments must be in the
    *tool's own row*.
    """
    agents = read("docs", "agents.md")
    rows: dict[str, str] = {}
    for line in agents.splitlines():
        match = re.match(r"\|\s*`(tos_[a-z_]+)`\s*\|([^|]*)\|", line)
        if match:
            rows[match.group(1)] = match.group(2)
    return rows


def test_every_mcp_tool_is_documented_with_its_arguments():
    rows = mcp_table_rows()
    missing: list[str] = []
    for tool in mcp_tools():
        name = tool["name"]
        if name not in rows:
            missing.append(f"tool {name} is not a row in the MCP table")
            continue
        cell = rows[name]
        for prop in tool["inputSchema"].get("properties", {}):
            if f"`{prop}`" not in cell:
                missing.append(f"{name} row does not list argument {prop}")
    assert not missing, "undocumented MCP surface:\n  " + "\n  ".join(missing)


def test_mcp_documents_every_error_code_it_can_return():
    """The protocol section must name each JSON-RPC error the server can emit."""
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from tos_toolkit import mcp

    commands = read("docs", "commands.md")
    for code, label in [
        (mcp.PARSE_ERROR, "parse error"),
        (mcp.INVALID_REQUEST, "invalid request"),
        (mcp.METHOD_NOT_FOUND, "method not found"),
        (mcp.INVALID_PARAMS, "invalid parameters"),
    ]:
        assert str(code) in commands, f"error code {code} ({label}) is undocumented"


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
    """Every key a user can write must be documented, from every source of keys.

    The profile files alone are not the surface: `[parser]`, `[review]`,
    `kind_dirs` and `templates_dir` never appear in them.
    """
    configuration = read("docs", "configuration.md")
    keys: set[str] = set()

    for profile in sorted((ROOT / "src" / "tos_toolkit" / "data" / "profiles").glob("*.toml")):
        for section, values in tomllib.loads(profile.read_text(encoding="utf-8")).items():
            keys.update(f"{section}.{key}" for key in values)

    # Keys read by config.load() but absent from every profile.
    from_source = read("src", "tos_toolkit", "config.py")
    for section_key in re.findall(r'section\.get\("([a-z_]+)"', from_source):
        keys.add(section_key)
    for section in ("project", "header", "parser", "review", "checks"):
        for literal in re.findall(rf'if "([a-z_]+)" in {section}:', from_source):
            keys.add(f"{section}.{literal}")

    # The generated template is the example every user starts from.
    keys.update(
        f"project.{key}" for key in re.findall(r"^templates_dir", read("src", "tos_toolkit", "scaffold.py"), re.M)
    )

    missing = sorted(
        key
        for key in keys
        if key.split(".", 1)[-1] not in configuration
        and f"`{key}`" not in configuration
    )
    assert not missing, (
        "tos.toml keys not documented in docs/configuration.md:\n  " + "\n  ".join(missing)
    )


def test_configuration_documents_every_section():
    configuration = read("docs", "configuration.md")
    for section in ("[profile]", "[project]", "[header]", "[parser]", "[review]", "[checks]"):
        assert section in configuration, f"docs/configuration.md never shows {section}"


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
