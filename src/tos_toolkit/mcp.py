"""Model Context Protocol server over stdio.

Exposes the toolkit to coding assistants as native tools instead of asking them
to shell out and parse a CLI:

``tos_lint``           static analysis with structured findings
``tos_explain``        is this ThinkScript function real, and how confident are we
``tos_docs``           the bundled knowledge base (list, read, or search)
``tos_syntax_check``   grammar check via a local thinkorswim install

Design notes
------------
* JSON-RPC 2.0, one JSON object per line, on stdin/stdout. Nothing else may be
  written to stdout or the stream is corrupted, so all diagnostics go to stderr.
* No dependencies. The MCP SDK is not required for the stdio transport; the
  shipped package stays dependency-free.
* ``isError`` means **the tool call failed**, not that the code under analysis has
  problems. A lint run that finds errors returns normally, with the findings in
  the payload: an agent should read them, not treat the call as broken.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from typing import Any, Callable

from . import __version__
from .checks import Context, run_all
from .config import Config, ConfigError, load as load_config
from .diagnostics import Level
from .registry import load as load_registry

SERVER_NAME = "tos-toolkit"

# Newest first. We echo the client's version when we know it, else offer ours.
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_PROTOCOL = SUPPORTED_PROTOCOLS[0]

# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class ToolError(Exception):
    """A tool call failed for an operational reason (not a finding)."""


TOOLS: list[dict[str, Any]] = [
    {
        "name": "tos_lint",
        "description": (
            "Statically analyse ThinkScript (.thinkscript) files. Catches the "
            "failures that only surface in thinkorswim: case-insensitive "
            "identifier collisions (E071), '//' used as a comment (E003), "
            "chart-only functions inside scans (E401), unknown function names "
            "(E072), and header/validation-state problems. Returns structured "
            "findings with file, line and a stable diagnostic code. Finding "
            "problems is a successful call; check the returned error count."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Files or directories to check. Omit to use the "
                        "configured targets from tos.toml."
                    ),
                },
                "profile": {
                    "type": "string",
                    "enum": ["strict", "loose"],
                    "description": (
                        "strict enforces house conventions (header block, "
                        "@status, layout). loose keeps only language rules."
                    ),
                },
                "strict": {
                    "type": "boolean",
                    "description": "Treat warnings as failures. Default false.",
                },
            },
        },
    },
    {
        "name": "tos_explain",
        "description": (
            "Look up a ThinkScript function or enum constant in the curated "
            "registry and report its confidence. Use this before writing a call "
            "you are not sure exists: inventing a function is the most common "
            "ThinkScript mistake, and the platform rejects the whole study for "
            "it. Also accepts dotted constant members such as 'Color.LIGHT_RED'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Function name or Namespace.MEMBER, e.g. 'TrueRange' or 'PriceType.BID'.",
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "tos_docs",
        "description": (
            "Read the bundled ThinkScript knowledge base: language reference, "
            "function signatures, constants, gotchas (NaN propagation, rec rules, "
            "fold, platform limits), asset-class specifics, artifact restrictions, "
            "and a list of keywords that exist but are unverified. Call with no "
            "arguments to list topics."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic file stem, e.g. 'gotchas', 'functions', 'unverified-tokens'.",
                },
                "grep": {
                    "type": "string",
                    "description": "Search the whole knowledge base for this text instead.",
                },
            },
        },
    },
    {
        "name": "tos_syntax_check",
        "description": (
            "Validate grammar using the REAL thinkorswim parser from the user's "
            "own installation. Stronger than lint for syntax, but weaker for "
            "meaning: it accepts a correctly-shaped call to a function that does "
            "not exist. Reports unavailable (not failure) when thinkorswim or a "
            "JDK is missing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files or directories to check. Omit for configured targets.",
                }
            },
        },
    },
]


# --------------------------------------------------------------------------- #
# tool implementations
# --------------------------------------------------------------------------- #


def _config_for(base: Config, args: dict[str, Any], profile: str | None = None) -> Config:
    """Resolve a profile override against the SAME tos.toml the CLI loaded.

    Re-discovering from the working directory would silently drop an explicit
    --config, which changes which rules are enabled and can flip a failing lint
    into a passing one.
    """
    profile_name = args.get("profile") or profile
    if not profile_name:
        return base
    try:
        return load_config(config_path=base.config_path, profile=profile_name)
    except ConfigError as exc:
        raise ToolError(str(exc)) from exc


def _display_path(path, root) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _stray_for(config: Config, paths: list[str]) -> list:
    """The .ts files a lint run should report, resolved the same way as targets."""
    from .cli import _walk

    targets = paths or [
        str(config.root / target)
        for target in config.targets
        if (config.root / target).exists()
    ]
    if not targets:
        return []
    try:
        _files, stray = _walk(targets, config.root, strict_paths=False)
    except SystemExit:
        return []
    return stray


def _walk_targets(config: Config, paths: list[str]) -> list:
    from .cli import THINKSSCRIPT_SUFFIX, _walk

    targets = paths or [
        str(config.root / target)
        for target in config.targets
        if (config.root / target).exists()
    ]
    if not targets:
        raise ToolError(
            "no targets: pass 'paths', or run 'tos init' to create the artifact "
            "directories, or add [project] targets to tos.toml"
        )
    try:
        files, _stray = _walk(targets, config.root, strict_paths=bool(paths))
    except SystemExit as exc:
        # The CLI exits 2 on a bad path; inside the server that must be a tool
        # error, never a process exit — killing the loop drops the client.
        raise ToolError(
            f"path not found: {', '.join(paths)}" if paths else "no valid target paths"
        ) from exc
    if not files:
        raise ToolError(f"no {THINKSSCRIPT_SUFFIX} files found under: {', '.join(paths) or 'configured targets'}")
    return files


def _tool_lint(args: dict[str, Any], config: Config) -> tuple[str, bool]:
    active = _config_for(config, args)
    registry = load_registry()
    paths = list(args.get("paths") or [])
    stray = _stray_for(active, paths)
    try:
        files = _walk_targets(active, paths)
    except ToolError:
        # A directory containing only .ts files is not an operational failure:
        # E005 findings are the answer. Only re-raise when there is nothing to say.
        if not stray:
            raise
        files = []

    findings: list[dict[str, Any]] = []
    errors = warnings = 0

    # A .ts file collides with TypeScript and is an error in the CLI; dropping it
    # here would make the same tree pass over MCP and fail in CI.
    stray_level = active.level("E005")
    if stray_level is not Level.OFF:
        for path in stray:
            finding = {
                "path": _display_path(path, active.root),
                "line": 0,
                "code": "E005",
                "severity": "error" if stray_level is Level.ERROR else "warning",
                "message": f"'{path.name}' collides with TypeScript; rename to .thinkscript",
                "hint": None,
            }
            findings.append(finding)
            if finding["severity"] == "error":
                errors += 1
            else:
                warnings += 1
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            raise ToolError(f"cannot read {path}: {exc}") from exc
        ctx = Context(path=path, root=active.root, text=text, config=active, registry=registry)
        for finding in run_all(ctx):
            findings.append(
                {
                    "path": finding.path,
                    "line": finding.line,
                    "code": finding.code,
                    "severity": finding.severity,
                    "message": finding.message,
                    "hint": finding.hint,
                }
            )
            if finding.is_error:
                errors += 1
            elif finding.is_warning:
                warnings += 1

    ok = errors == 0 and not (args.get("strict") and warnings)
    payload = {
        "ok": ok,
        "profile": active.profile,
        "files_checked": len(files),
        "error_count": errors,
        "warning_count": warnings,
        "findings": findings,
    }
    return json.dumps(payload, indent=2), False


def _tool_explain(args: dict[str, Any], config: Config) -> tuple[str, bool]:
    name = (args.get("name") or "").strip()
    if not name:
        raise ToolError("'name' is required")
    registry = load_registry()

    info = registry.function(name)
    if info is not None:
        lines = [f"{info.name}  [{info.category}]  confidence={info.confidence}"]
        if info.notes:
            lines.append(f"  {info.notes}")
        if info.is_unverified:
            lines.append(
                "  WARNING: unverified. Paste-test it in thinkorswim before relying on it."
            )
        return "\n".join(lines), False

    if "." in name:
        namespace, member = name.split(".", 1)
        if registry.has_namespace(namespace):
            if member.lower() in registry.namespace_members(namespace):
                return f"{name}: valid {namespace} member", False
            known = ", ".join(sorted(registry.namespace_members(namespace)))
            return f"{name}: NOT a known {namespace} member\n  known: {known}", False

    return (
        f"'{name}' is not in the curated registry.\n"
        "That does not mean it is invalid — the registry is not exhaustive. "
        "Verify it in the platform before shipping.",
        False,
    )


def _tool_docs(args: dict[str, Any], config: Config) -> tuple[str, bool]:
    from . import knowledge

    if args.get("grep"):
        hits = knowledge.search(str(args["grep"]))
        if not hits:
            return f"No matches for {args['grep']!r}.", False
        return "\n".join(f"{slug}:{line}: {text}" for slug, line, text in hits), False

    topic = args.get("topic")
    if topic:
        body = knowledge.read(str(topic))
        if body is None:
            available = ", ".join(slug for slug, _ in knowledge.topics())
            raise ToolError(f"unknown topic {topic!r}. Available: {available}")
        return body, False

    listing = "\n".join(f"{slug:<24} {title}" for slug, title in knowledge.topics())
    return f"Topics:\n{listing}\n\nCall tos_docs again with a 'topic'.", False


def _tool_syntax_check(args: dict[str, Any], config: Config) -> tuple[str, bool]:
    from .parser import bridge

    files = _walk_targets(config, list(args.get("paths") or []))
    if not config.parser_enabled:
        raise ToolError(
            "grammar checking is disabled in tos.toml ([parser] enabled = false)"
        )
    try:
        runtimes = bridge.prepare(config.tos_path)
    except bridge.ParserUnavailable as exc:
        raise ToolError(
            f"grammar check unavailable: {exc}\n"
            "It requires a local thinkorswim install and a JDK. Everything else "
            "works without it — fall back to tos_lint."
        ) from exc

    lines: list[str] = []
    failures = 0
    for path in files:
        status, messages = bridge.check_file(path, runtimes)
        if status == bridge.OK:
            lines.append(f"OK (grammar only): {path}")
        elif status == bridge.ERROR:
            raise ToolError(
                "the parser could not run, so nothing was verified:\n"
                + "\n".join(messages)
            )
        else:
            failures += 1
            lines.append(f"FAIL: {path}")
            lines.extend(f"  {message}" for message in messages)
    lines.append("")
    lines.append(
        f"{len(files)} file(s) checked, {failures} with grammar errors. "
        "Grammar only: function names and semantics are not verified."
    )
    return "\n".join(lines), False


HANDLERS: dict[str, Callable[[dict[str, Any], Config], tuple[str, bool]]] = {
    "tos_lint": _tool_lint,
    "tos_explain": _tool_explain,
    "tos_docs": _tool_docs,
    "tos_syntax_check": _tool_syntax_check,
}


# --------------------------------------------------------------------------- #
# JSON-RPC
# --------------------------------------------------------------------------- #


def _result(request_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _text(body: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": body}], "isError": is_error}


def handle(request: dict[str, Any], config: Config) -> dict[str, Any] | None:
    """Handle one JSON-RPC message. Returns a response, or None for a notification."""
    request_id = request.get("id")
    method = request.get("method")

    if not isinstance(method, str):
        return _error(request_id, INVALID_REQUEST, "missing 'method'")

    is_notification = "id" not in request
    params = request.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        # A malformed params value must be an error response, not an exception
        # that unwinds serve() and drops the client.
        return _error(request_id, INVALID_PARAMS, "'params' must be an object")
    if is_notification:
        # JSON-RPC: a notification never gets a response, including for ping or
        # an unknown method. We have no server-initiated work to do here.
        return None

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOLS else DEFAULT_PROTOCOL
        return _result(
            request_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": __version__},
                "instructions": (
                    "ThinkScript analysis for thinkorswim. Before writing a "
                    "study, call tos_docs for the language rules and tos_explain "
                    "for any function you are not certain exists. After editing, "
                    "call tos_lint and fix every error. Never claim a script "
                    "works: only pasting it into thinkorswim proves that."
                ),
            },
        )

    if method in {"notifications/initialized", "initialized", "notifications/cancelled"}:
        return None

    if method == "ping":
        return _result(request_id, {})

    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str) or not name:
            return _error(request_id, INVALID_PARAMS, "'name' must be a non-empty string")
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        handler = HANDLERS.get(name)
        if handler is None:
            return _error(request_id, INVALID_PARAMS, f"unknown tool {name!r}")
        if not isinstance(arguments, dict):
            return _error(request_id, INVALID_PARAMS, "'arguments' must be an object")
        try:
            body, is_error = handler(arguments, config)
        except ToolError as exc:
            return _result(request_id, _text(str(exc), is_error=True))
        except SystemExit:
            # A CLI helper called exit(); the server must not.
            return _result(
                request_id,
                _text(f"{name} aborted while handling the request", is_error=True),
            )
        except Exception as exc:  # noqa: BLE001 - never kill the server loop
            print(f"tos mcp: tool {name} failed: {exc}", file=sys.stderr)
            return _result(
                request_id, _text(f"{name} failed unexpectedly: {exc}", is_error=True)
            )
        return _result(request_id, _text(body, is_error=is_error))

    if method in {"resources/list", "prompts/list"}:
        key = "resources" if method.startswith("resources") else "prompts"
        return _result(request_id, {key: []})

    if is_notification:
        return None
    return _error(request_id, METHOD_NOT_FOUND, f"unknown method {method!r}")


def serve(config: Config, stdin=None, stdout=None) -> int:
    """Run the stdio loop until EOF."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    for raw in stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            stdout.write(json.dumps(_error(None, PARSE_ERROR, f"invalid JSON: {exc}")) + "\n")
            stdout.flush()
            continue
        if not isinstance(request, dict):
            stdout.write(
                json.dumps(_error(None, INVALID_REQUEST, "expected a JSON object")) + "\n"
            )
            stdout.flush()
            continue

        response = handle(request, config)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
    return 0
