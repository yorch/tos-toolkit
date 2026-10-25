"""Lexer tests: the parts that are easy to get subtly wrong."""

from __future__ import annotations

from tos_toolkit.lexer import (
    Kind,
    find_calls,
    split_statements,
    strip_comments_and_strings,
    tokenize,
)


def test_hash_is_a_comment_but_double_slash_is_not():
    tokens = tokenize("def a = 1; # a comment\ndef b = 2 / 3;")
    idents = [t.value for t in tokens if t.kind is Kind.IDENT]
    assert "comment" not in idents
    assert "a" in idents and "b" in idents


def test_string_bodies_are_not_tokenized():
    tokens = tokenize('AddLabel(yes, "PDH 4718.25 # not a comment", Color.GRAY);')
    strings = [t.value for t in tokens if t.kind is Kind.STRING]
    assert strings == ["PDH 4718.25 # not a comment"]


def test_statements_split_on_top_level_semicolons():
    text = "def a = 1;\ndef b = 2;\n"
    statements = split_statements(tokenize(text))
    assert [s.keyword for s in statements] == ["def", "def"]
    assert all(s.terminated for s in statements)


def test_statements_span_physical_lines():
    text = "rec x = if cond\n          then 1\n          else x[1];\n"
    statements = split_statements(tokenize(text))
    assert len(statements) == 1
    assert statements[0].keyword == "rec"


def test_semicolon_inside_parens_does_not_split():
    # Not valid ThinkScript, but the splitter must not be fooled by depth.
    text = "def a = Max(1, 2;\n"
    statements = split_statements(tokenize(text))
    assert len(statements) == 1


def test_line_numbers_are_preserved_across_multiline_strings():
    text = 'plot x = close;\nAddLabel(yes, "a\nb",\n                     Color.GRAY);\n'
    tokens = tokenize(text)
    gray = next(t for t in tokens if t.value == "Color")
    assert gray.line == 4


def test_find_calls_ignores_method_calls_on_plots():
    text = "plot FastLine = ExpAverage(close, 8);\nFastLine.SetDefaultColor(Color.GREEN);\n"
    calls = find_calls(split_statements(tokenize(text)))
    names = {c.value for c in calls}
    assert "ExpAverage" in names
    assert "SetDefaultColor" not in names  # preceded by '.'


def test_strip_comments_and_strings_preserves_positions():
    text = 'def a = 1; # x\nAddLabel(yes, "hi");\n'
    masked = strip_comments_and_strings(text)
    lines = masked.splitlines()
    assert len(lines) == 2
    assert "x" not in lines[0]
    assert "hi" not in lines[1]
    assert len(lines[1]) == len('AddLabel(yes, "hi");')


def test_bracket_depth_tracked():
    tokens = tokenize("def a = Max(1, Min(2, 3));")
    closers = [t for t in tokens if t.kind is Kind.RPAREN]
    assert [t.depth for t in closers] == [1, 0]
