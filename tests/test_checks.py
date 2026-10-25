"""Rule tests: one fixture per diagnostic code."""

from __future__ import annotations

from pathlib import Path

from conftest import codes, make_ctx

from tos_toolkit.checks import run_all

STUDY = """\
# @name: Sample
# @kind: study
# @panel: upper
# @assets: index
# @timeframes: intraday
# @version: 0.1.0
# @status: draft
# @inputs: length=14

declare upper;

input length = 14;

def computed = Average(close, length);

plot Value = computed;
Value.SetDefaultColor(Color.GREEN);
"""

SCAN = """\
# @name: Sample Scan
# @kind: scan
# @panel: none
# @assets: stock
# @timeframes: daily
# @version: 0.1.0
# @status: draft
# @inputs: length=14

input length = 14;

def avg = Average(close, length);

plot Scan = close > avg;
"""

COLUMN = """\
# @name: Sample Column
# @kind: column
# @panel: none
# @assets: stock
# @timeframes: daily
# @version: 0.1.0
# @status: draft
# @inputs: length=14

input length = 14;

def avg = Average(close, length);

plot Value = close - avg;
"""


def _findings(tmp_path, text, **kwargs):
    return run_all(make_ctx(tmp_path, text, **kwargs))


# --------------------------------------------------------------------------
# clean baselines


def test_study_is_clean(tmp_path):
    findings = _findings(tmp_path, STUDY)
    assert [f for f in findings if f.is_error] == []


def test_scan_is_clean(tmp_path):
    findings = _findings(tmp_path, SCAN, subdir="scans", filename="sample_scan.thinkscript")
    assert [f for f in findings if f.is_error] == []


def test_column_is_clean(tmp_path):
    findings = _findings(
        tmp_path, COLUMN, subdir="columns", filename="sample_col.thinkscript"
    )
    assert [f for f in findings if f.is_error] == []


# --------------------------------------------------------------------------
# Layer 1 — lexical


def test_tab_is_an_error(tmp_path):
    text = "declare upper;\ndef x = 1;\n\tdef y = 2;\n"
    assert "E001" in codes(_findings(tmp_path, text, profile="loose"))


def test_missing_trailing_newline(tmp_path):
    assert "E002" in codes(_findings(tmp_path, STUDY.rstrip("\n")))


def test_double_slash_is_not_a_comment(tmp_path):
    text = "declare upper;\ndef x = close; // nope\n"
    assert "E003" in codes(_findings(tmp_path, text, profile="loose"))


def test_unbalanced_delimiter(tmp_path):
    text = "declare upper;\ndef x = Max(1, 2;\n"
    assert "E004" in codes(_findings(tmp_path, text, profile="loose"))


# --------------------------------------------------------------------------
# Layer 1 — identifiers


def test_duplicate_identifier(tmp_path):
    text = "declare upper;\ndef a = 1;\ndef a = 2;\n"
    assert "E070" in codes(_findings(tmp_path, text, profile="loose"))


def test_case_insensitive_collision_is_an_error(tmp_path):
    """The bug that actually broke a paste: rec pdHigh vs plot PdHigh."""
    text = (
        "declare upper;\n"
        "rec pdHigh = if BarNumber() == 1 then high else pdHigh[1];\n"
        "plot PdHigh = pdHigh;\n"
    )
    findings = _findings(tmp_path, text, profile="loose")
    collisions = [f for f in findings if f.code == "E071"]
    assert collisions, codes(findings)
    assert collisions[0].is_error


def test_unknown_function_warns_by_default(tmp_path):
    text = "declare upper;\ndef x = FooBarNotAFunction(close);\n"
    findings = _findings(tmp_path, text, profile="loose")
    unknown = [f for f in findings if f.code == "E072"]
    assert unknown, codes(findings)
    assert unknown[0].is_warning


def test_unknown_function_can_be_escalated(tmp_path):
    from tos_toolkit.diagnostics import Level

    text = "declare upper;\ndef x = FooBarNotAFunction(close);\n"
    findings = _findings(
        tmp_path, text, profile="loose", rules={"unknown_functions": Level.ERROR}
    )
    unknown = [f for f in findings if f.code == "E072"]
    assert unknown and unknown[0].is_error


def test_locally_declared_names_are_not_unknown(tmp_path):
    text = (
        "declare upper;\n"
        "def helper = close * 2;\n"
        "plot Y = helper;\n"
    )
    assert "E072" not in codes(_findings(tmp_path, text, profile="loose"))


def test_script_block_names_are_not_unknown(tmp_path):
    text = (
        "declare upper;\n"
        "script scaled { input a = 0; plot out = a * 2; }\n"
        "plot Y = scaled(close);\n"
    )
    assert "E072" not in codes(_findings(tmp_path, text, profile="loose"))


def test_bare_assignment_is_an_error(tmp_path):
    text = "declare upper;\nx = 1;\n"
    assert "E073" in codes(_findings(tmp_path, text, profile="loose"))


# --------------------------------------------------------------------------
# Layer 2 — header (profile-gated)


def test_missing_header_is_layer2_only(tmp_path):
    bare = "declare upper;\nplot x = close;\n"
    assert "E101" in codes(_findings(tmp_path, bare, profile="strict"))
    assert "E101" not in codes(_findings(tmp_path, bare, profile="loose"))


def test_missing_required_key(tmp_path):
    text = STUDY.replace("# @status: draft\n", "")
    assert "E102" in codes(_findings(tmp_path, text))


def test_invalid_status_value(tmp_path):
    text = STUDY.replace("# @status: draft", "# @status: shipped")
    assert "E103" in codes(_findings(tmp_path, text))


def test_panel_must_be_none_for_scan(tmp_path):
    text = SCAN.replace("# @panel: none", "# @panel: upper")
    findings = _findings(tmp_path, text, subdir="scans", filename="sample_scan.thinkscript")
    assert "E103" in codes(findings)


def test_inputs_missing_entry(tmp_path):
    text = STUDY.replace("# @inputs: length=14\n", "")
    assert "E104" in codes(_findings(tmp_path, text))


def test_inputs_documents_nonexistent(tmp_path):
    text = STUDY.replace("# @inputs: length=14", "# @inputs: length=14, ghost=1")
    assert "W103" in codes(_findings(tmp_path, text))


def test_inputs_order_mismatch(tmp_path):
    text = (
        STUDY.replace("# @inputs: length=14", "# @inputs: length=14, beta=2")
        .replace("input length = 14;", "input beta = 2;\ninput length = 14;")
    )
    assert "W104" in codes(_findings(tmp_path, text))


# --------------------------------------------------------------------------
# Layer 2 — layout


def test_kind_directory_mismatch(tmp_path):
    findings = _findings(tmp_path, SCAN)  # SCAN sitting in studies/trend
    assert "E120" in codes(findings)


def test_naming_convention_warns(tmp_path):
    findings = _findings(
        tmp_path, SCAN, subdir="scans", filename="NotSnake.ts.thinkscript"
    )
    assert "W080" in codes(findings)


def test_scan_suffix_warns(tmp_path):
    findings = _findings(tmp_path, SCAN, subdir="scans", filename="sample.thinkscript")
    assert "W081" in codes(findings)


# --------------------------------------------------------------------------
# Layer 1 — artifact rules


def test_scan_cannot_draw(tmp_path):
    text = SCAN.replace(
        'plot Scan = close > avg;',
        'AddLabel(yes, "x", Color.GRAY);\nplot Scan = close > avg;',
    )
    findings = _findings(tmp_path, text, subdir="scans", filename="sample_scan.thinkscript")
    assert "E401" in codes(findings)


def test_scan_must_end_with_plot(tmp_path):
    text = SCAN.replace("plot Scan = close > avg;", "def Scan = close > avg;")
    findings = _findings(tmp_path, text, subdir="scans", filename="sample_scan.thinkscript")
    assert "E403" in codes(findings)


def test_scan_constant_plot_warns(tmp_path):
    text = SCAN.replace("plot Scan = close > avg;", "plot Scan = yes;")
    findings = _findings(tmp_path, text, subdir="scans", filename="sample_scan.thinkscript")
    assert "W402" in codes(findings)


def test_column_rejects_extra_plots(tmp_path):
    text = COLUMN + "\nplot Extra = close;\n"
    findings = _findings(tmp_path, text, subdir="columns", filename="sample_col.thinkscript")
    assert "E404" in codes(findings)


def test_column_allows_addlabel_and_background(tmp_path):
    text = COLUMN + '\nAddLabel(yes, "ok", Color.GRAY);\nAssignBackgroundColor(Color.GRAY);\n'
    findings = _findings(tmp_path, text, subdir="columns", filename="sample_col.thinkscript")
    assert "E402" not in codes(findings)


def test_column_rejects_assign_price_color(tmp_path):
    text = COLUMN + "\nAssignPriceColor(Color.GREEN);\n"
    findings = _findings(tmp_path, text, subdir="columns", filename="sample_col.thinkscript")
    assert "E402" in codes(findings)


# --------------------------------------------------------------------------
# Unverified platform behaviour


def test_rec_self_reference_depth_warns(tmp_path):
    text = "declare upper;\nrec x = if BarNumber() == 1 then 1 else x[2] + 1;\nplot X = x;\n"
    assert "W091" in codes(_findings(tmp_path, text, profile="loose"))


def test_one_reference_per_branch_is_not_flagged(tmp_path):
    """`if c then x[1] + 1 else x[1]` is the ordinary rec form."""
    text = (
        "declare upper;\n"
        "rec x = if BarNumber() == 1 then 1 else Max(x[1], x[1]);\n"
        "plot X = x;\n"
    )
    assert "W090" not in codes(_findings(tmp_path, text, profile="loose"))


def test_three_self_references_warn(tmp_path):
    text = (
        "declare upper;\n"
        "rec x = if BarNumber() == 1 then 1 else Max(x[1], Max(x[1], x[1]));\n"
        "plot X = x;\n"
    )
    assert "W090" in codes(_findings(tmp_path, text, profile="loose"))


# --------------------------------------------------------------------------
# File discovery


def test_stray_ts_extension_detected(tmp_path):
    from tos_toolkit.cli import _walk

    (tmp_path / "studies").mkdir()
    (tmp_path / "studies" / "bad.ts").write_text("plot x = close;")
    files, stray = _walk([str(tmp_path / "studies")], Path(tmp_path))
    assert not files
    assert [p.name for p in stray] == ["bad.ts"]


# --------------------------------------------------------------------------
# regressions found by adversarial review


def test_statement_after_script_block_is_parsed_separately(tmp_path):
    """A `script {}` block has no trailing ';' — the next statement must not merge."""
    text = (
        "declare upper;\n"
        "script scaled { input a = 0; plot out = a * 2; }\n"
        "def foo = scaled(close);\n"
        "plot Foo = foo;\n"
    )
    findings = _findings(tmp_path, text, profile="loose")
    assert "E071" in codes(findings), codes(findings)


def test_single_self_reference_does_not_warn(tmp_path):
    text = (
        "declare upper;\n"
        "rec x = if BarNumber() == 1 then 1 else x[1] + 1;\n"
        "plot X = x;\n"
    )
    assert "W090" not in codes(_findings(tmp_path, text, profile="loose"))


def test_keywords_are_not_unknown_functions(tmp_path):
    text = (
        "declare upper;\n"
        "def x = fold i = 0 to 3 with acc = 0 do acc + i;\n"
        "plot X = x;\n"
    )
    assert "E072" not in codes(_findings(tmp_path, text, profile="loose"))


def test_missing_explicit_path_is_an_error(tmp_path, monkeypatch):
    from tos_toolkit.cli import main

    monkeypatch.chdir(tmp_path)
    try:
        code = main(["--profile", "loose", "lint", "nope.thinkscript"])
    except SystemExit as exc:  # strict_paths raises
        code = exc.code
    assert code != 0


def test_def_def_case_pair_is_flagged(tmp_path):
    text = "declare upper;\ndef pdHigh = 1;\ndef PdHigh = 2;\nplot Y = pdHigh;\n"
    findings = _findings(tmp_path, text, profile="loose")
    assert "E070" in codes(findings), codes(findings)


def test_input_def_case_pair_is_flagged(tmp_path):
    text = "declare upper;\ninput Length = 14;\ndef length = 2;\nplot Y = length;\n"
    findings = _findings(tmp_path, text, profile="loose")
    assert "E070" in codes(findings), codes(findings)


def test_plot_def_pair_is_e071_only(tmp_path):
    text = "declare upper;\ndef pdHigh = 1;\nplot PdHigh = pdHigh;\n"
    found = codes(_findings(tmp_path, text, profile="loose"))
    assert "E071" in found
    assert "E070" not in found


def test_if_else_brace_chain_is_not_split_into_else_statements(tmp_path):
    from tos_toolkit.lexer import split_statements, tokenize

    text = "def x = 1;\nif c { def a = 1; } else { def b = 2; }\nplot Y = x;\n"
    statements = split_statements(tokenize(text))
    assert all(s.keyword != "else" for s in statements)


# --------------------------------------------------------------------------
# restored checks (regressions found when migrating a consumer repo)


def test_study_must_open_with_declare(tmp_path):
    text = STUDY.replace("declare upper;\n\n", "")
    assert "E031" in codes(_findings(tmp_path, text))


def test_scan_is_exempt_from_declare_rule(tmp_path):
    findings = _findings(tmp_path, SCAN, subdir="scans", filename="sample_scan.thinkscript")
    assert "E031" not in codes(findings)


def test_option_function_requires_option_asset(tmp_path):
    text = STUDY.replace(
        "plot Value = computed;", "plot Value = GetATMOption(close, 1, 1);"
    )
    findings = _findings(tmp_path, text)
    assert "E050" in codes(findings), codes(findings)


def test_option_asset_declared_is_fine(tmp_path):
    text = STUDY.replace("# @assets: index", "# @assets: index, option").replace(
        "plot Value = computed;", "plot Value = GetATMOption(close, 1, 1);"
    )
    findings = _findings(tmp_path, text)
    assert "E050" not in codes(findings)


def test_repaint_honesty(tmp_path):
    text = (
        STUDY.replace("# @version: 0.1.0", "# @version: 0.1.0\n# @repaints: no")
        .replace(
            "plot Value = computed;",
            "def dailyClose = close(period = AggregationPeriod.DAY);\nplot Value = dailyClose;",
        )
    )
    findings = _findings(tmp_path, text)
    assert "W050" in codes(findings), codes(findings)


def test_repaint_declared_yes_is_fine(tmp_path):
    text = (
        STUDY.replace("# @version: 0.1.0", "# @version: 0.1.0\n# @repaints: yes")
        .replace(
            "plot Value = computed;",
            "def dailyClose = close(period = AggregationPeriod.DAY);\nplot Value = dailyClose;",
        )
    )
    findings = _findings(tmp_path, text)
    assert "W050" not in codes(findings)


# --------------------------------------------------------------------------
# regressions found by the public-release audit (codex + claude)


def test_constant_namespace_lookup_is_case_insensitive(tmp_path):
    from tos_toolkit.registry import load as load_registry

    registry = load_registry()
    assert registry.has_namespace("Color")
    assert registry.has_namespace("color")
    assert "light_red" in registry.namespace_members("Color")
    assert "light_red" in registry.namespace_members("COLOR")


def test_chart_only_detection_is_case_insensitive(tmp_path):
    text = SCAN.replace(
        "plot Scan = close > avg;",
        'addlabel(yes, "x", Color.GRAY);\nplot Scan = close > avg;',
    )
    findings = _findings(tmp_path, text, subdir="scans", filename="sample_scan.thinkscript")
    assert "E401" in codes(findings), codes(findings)


def test_layout_rules_off_when_header_mode_off(tmp_path):
    """loose must not complain about kind-vs-directory or naming."""
    findings = _findings(
        tmp_path, SCAN, profile="loose", subdir="scans", filename="NotSnake.thinkscript"
    )
    found = codes(findings)
    assert "E120" not in found
    assert "W080" not in found
