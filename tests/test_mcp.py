"""MCP server tests: the JSON-RPC surface an assistant actually talks to."""

from __future__ import annotations

import json

import pytest
from conftest import make_ctx  # noqa: F401  (ensures tmp_path fixtures import)

from tos_toolkit import mcp
from tos_toolkit.config import Config


@pytest.fixture()
def config(tmp_path):
    cfg = Config(root=tmp_path)
    cfg.header_mode = "off"
    cfg.targets = []
    return cfg


def call(method, params=None, request_id=1):
    request = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    return request


def test_initialize_echoes_a_supported_protocol(config):
    response = mcp.handle(call("initialize", {"protocolVersion": "2025-06-18"}), config)
    assert response["result"]["protocolVersion"] == "2025-06-18"
    assert response["result"]["serverInfo"]["name"] == "tos-toolkit"
    assert "tools" in response["result"]["capabilities"]


def test_initialize_negotiates_unknown_protocol_down(config):
    response = mcp.handle(call("initialize", {"protocolVersion": "1999-01-01"}), config)
    assert response["result"]["protocolVersion"] in mcp.SUPPORTED_PROTOCOLS


def test_initialized_notification_gets_no_response(config):
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, config) is None


def test_tools_list_is_well_formed(config):
    tools = mcp.handle(call("tools/list"), config)["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert names == {"tos_lint", "tos_explain", "tos_docs", "tos_syntax_check"}
    for tool in tools:
        assert tool["description"]
        assert tool["inputSchema"]["type"] == "object"


def test_explain_known_function(config):
    response = mcp.handle(
        call("tools/call", {"name": "tos_explain", "arguments": {"name": "TrueRange"}}),
        config,
    )
    text = response["result"]["content"][0]["text"]
    assert "TrueRange" in text
    assert "confidence=" in text
    assert response["result"]["isError"] is False


def test_explain_unknown_function_is_not_an_error(config):
    """An unknown name is information, not a broken tool call."""
    response = mcp.handle(
        call("tools/call", {"name": "tos_explain", "arguments": {"name": "NoSuchFn"}}),
        config,
    )
    assert response["result"]["isError"] is False
    assert "not in the curated registry" in response["result"]["content"][0]["text"]


def test_explain_constant_member(config):
    response = mcp.handle(
        call("tools/call", {"name": "tos_explain", "arguments": {"name": "Color.LIGHT_RED"}}),
        config,
    )
    text = response["result"]["content"][0]["text"]
    assert "listed as a Color member" in text
    assert "curated, not authoritative" in text


def test_docs_lists_topics(config):
    response = mcp.handle(call("tools/call", {"name": "tos_docs", "arguments": {}}), config)
    text = response["result"]["content"][0]["text"]
    assert "gotchas" in text


def test_docs_reads_a_topic(config):
    response = mcp.handle(
        call("tools/call", {"name": "tos_docs", "arguments": {"topic": "gotchas"}}), config
    )
    assert "NaN" in response["result"]["content"][0]["text"]


def test_docs_unknown_topic_is_a_tool_error(config):
    response = mcp.handle(
        call("tools/call", {"name": "tos_docs", "arguments": {"topic": "nope"}}), config
    )
    assert response["result"]["isError"] is True


def test_lint_reports_findings_without_erroring(config, tmp_path):
    broken = tmp_path / "broken.thinkscript"
    broken.write_text(
        "declare upper;\n"
        "rec pdHigh = if BarNumber() == 1 then high else pdHigh[1];\n"
        "plot PdHigh = pdHigh;\n",
        encoding="utf-8",
    )
    response = mcp.handle(
        call(
            "tools/call",
            {"name": "tos_lint", "arguments": {"paths": [str(broken)], "profile": "loose"}},
        ),
        config,
    )
    result = response["result"]
    # Finding a problem is a successful call; the agent reads the payload.
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["ok"] is False
    assert payload["error_count"] == 1
    assert payload["findings"][0]["code"] == "E071"


def test_lint_clean_file(config, tmp_path):
    good = tmp_path / "good.thinkscript"
    good.write_text("declare upper;\nplot Value = close;\n", encoding="utf-8")
    response = mcp.handle(
        call(
            "tools/call",
            {"name": "tos_lint", "arguments": {"paths": [str(good)], "profile": "loose"}},
        ),
        config,
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["ok"] is True
    assert payload["error_count"] == 0


def test_lint_missing_path_is_a_tool_error(config):
    response = mcp.handle(
        call("tools/call", {"name": "tos_lint", "arguments": {"paths": ["nope.thinkscript"]}}),
        config,
    )
    assert response["result"]["isError"] is True


def test_unknown_tool_is_invalid_params(config):
    response = mcp.handle(call("tools/call", {"name": "nope", "arguments": {}}), config)
    assert response["error"]["code"] == mcp.INVALID_PARAMS


def test_unknown_method(config):
    response = mcp.handle(call("does/not/exist"), config)
    assert response["error"]["code"] == mcp.METHOD_NOT_FOUND


def test_serve_writes_one_json_object_per_line(config, tmp_path):
    import io

    stdin = io.StringIO(
        "\n".join(
            [
                json.dumps(call("initialize", {"protocolVersion": "2025-06-18"}, 1)),
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                json.dumps(call("tools/list", None, 2)),
            ]
        )
        + "\n"
    )
    stdout = io.StringIO()
    assert mcp.serve(config, stdin=stdin, stdout=stdout) == 0

    lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
    # The notification produced no response.
    assert len(lines) == 2
    assert json.loads(lines[0])["id"] == 1
    assert json.loads(lines[1])["id"] == 2


def test_serve_reports_parse_errors_without_dying(config):
    import io

    stdin = io.StringIO("not json\n" + json.dumps(call("ping", None, 9)) + "\n")
    stdout = io.StringIO()
    mcp.serve(config, stdin=stdin, stdout=stdout)
    responses = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    assert responses[0]["error"]["code"] == mcp.PARSE_ERROR
    assert responses[1]["result"] == {}


# --------------------------------------------------------------------------
# regressions from the adversarial review of the MCP server


def test_stray_ts_file_is_reported(config, tmp_path):
    """The CLI flags a .ts file as E005; MCP must not silently pass it."""
    (tmp_path / "a.thinkscript").write_text("declare upper;\nplot A = close;\n")
    (tmp_path / "stray.ts").write_text("plot x = close;\n")
    response = mcp.handle(
        call(
            "tools/call",
            {"name": "tos_lint", "arguments": {"paths": [str(tmp_path)], "profile": "loose"}},
        ),
        config,
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert "E005" in {f["code"] for f in payload["findings"]}
    assert payload["ok"] is False


def test_profile_override_keeps_the_loaded_config_file(tmp_path):
    """--config must not be discarded when a tool passes a profile."""
    from tos_toolkit.config import load

    project = tmp_path / "proj"
    project.mkdir()
    (project / "tos.toml").write_text(
        '[profile]\nname = "strict"\n\n[checks]\nunknown_functions = "error"\n',
        encoding="utf-8",
    )
    base = load(config_path=project / "tos.toml")
    assert base.level("unknown_functions") is not None

    overridden = mcp._config_for(base, {"profile": "loose"})
    # The file's own rule override must survive the profile change.
    from tos_toolkit.diagnostics import Level

    assert overridden.rules.get("unknown_functions") is Level.ERROR


def test_non_object_params_do_not_kill_the_server(config):
    response = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": ["bad"]}, config)
    assert response["error"]["code"] == mcp.INVALID_PARAMS


def test_non_string_tool_name_is_invalid_params(config):
    response = mcp.handle(
        call("tools/call", {"name": [], "arguments": {}}), config
    )
    assert response["error"]["code"] == mcp.INVALID_PARAMS


def test_missing_path_is_not_swallowed_by_stray_findings(config, tmp_path):
    """A missing path must stay an error even when a .ts file is also present."""
    (tmp_path / "stray.ts").write_text("plot x = close;\n")
    response = mcp.handle(
        call(
            "tools/call",
            {"name": "tos_lint", "arguments": {"paths": [str(tmp_path), "nope.thinkscript"]}},
        ),
        config,
    )
    assert response["result"]["isError"] is True
    assert "path not found" in response["result"]["content"][0]["text"]


def test_stray_only_directory_is_a_successful_finding(config, tmp_path):
    (tmp_path / "stray.ts").write_text("plot x = close;\n")
    response = mcp.handle(
        call("tools/call", {"name": "tos_lint", "arguments": {"paths": [str(tmp_path)]}}),
        config,
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["ok"] is False
    assert [f["code"] for f in payload["findings"]] == ["E005"]


def test_malformed_params_on_a_notification_gets_no_response(config):
    response = mcp.handle(
        {"jsonrpc": "2.0", "method": "ping", "params": []}, config
    )
    assert response is None


def test_nested_kind_directory_infers_kind(tmp_path):
    from conftest import make_ctx
    from tos_toolkit.checks import run_all
    from tos_toolkit.config import Config

    for depth in ("src/scans/x.thinkscript",):
        path = tmp_path / depth
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('AddLabel(yes, "x", Color.GRAY);\nplot Scan = close > 1;\n')
    cfg = Config(root=tmp_path)
    cfg.header_mode = "off"
    cfg.kind_dirs = {"scan": "src/scans"}
    from tos_toolkit.checks import Context
    from tos_toolkit.registry import load as load_registry

    ctx = Context(
        path=path, root=tmp_path, text=path.read_text(), config=cfg, registry=load_registry()
    )
    assert "E401" in {f.code for f in run_all(ctx)}


def test_split_declare_still_reports_e405(tmp_path):
    from conftest import make_ctx
    from tos_toolkit.checks import run_all

    ctx = make_ctx(
        tmp_path,
        "declare\nlower;\nplot Scan = close > 1;\n",
        profile="loose",
        subdir="scans",
        filename="x_scan.thinkscript",
    )
    assert "E405" in {f.code for f in run_all(ctx)}


def test_scan_with_no_statements_reports_e403(tmp_path):
    from conftest import make_ctx
    from tos_toolkit.checks import run_all

    ctx = make_ctx(
        tmp_path,
        "# @kind: scan\n\n",
        subdir="scans",
        filename="empty_scan.thinkscript",
    )
    assert "E403" in {f.code for f in run_all(ctx)}


def test_undecodable_file_does_not_abort_the_batch(config, tmp_path):
    """One bad encoding must not discard findings from the other files."""
    bad = tmp_path / "bad.thinkscript"
    bad.write_bytes(b"declare upper;\nplot A = \xff\xfe close;\n")
    good = tmp_path / "good.thinkscript"
    good.write_text(
        "declare upper;\nrec pdHigh = 1;\nplot PdHigh = pdHigh;\n", encoding="utf-8"
    )
    response = mcp.handle(
        call(
            "tools/call",
            {"name": "tos_lint", "arguments": {"paths": [str(tmp_path)], "profile": "loose"}},
        ),
        config,
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    found = {f["code"] for f in payload["findings"]}
    assert "E006" in found
    assert "E071" in found
