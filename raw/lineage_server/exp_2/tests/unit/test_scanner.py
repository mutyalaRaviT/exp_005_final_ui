from sas_lineage.scanner import (
    balanced_parentheses,
    find_statement_end,
    split_statements,
    strip_comments,
)


def test_strip_comments_block():
    assert strip_comments("data a; /* note ; */ set b;").split() == [
        "data", "a;", "set", "b;",
    ]


def test_strip_comments_keeps_quoted_text():
    assert strip_comments("x = '/* not a comment */';") == "x = '/* not a comment */';"


def test_find_statement_end_ignores_quoted_semicolons():
    text = "x = 'a;b'; y = 1;"
    assert text[find_statement_end(text)] == ";"
    assert find_statement_end(text) == 9


def test_split_statements():
    assert split_statements("data a;\n set b;\n run;") == ["data a", "set b", "run"]


def test_split_statements_multiline_statement():
    stmts = split_statements("set\n  raw.y(\n    keep=id\n  );\nrun;")
    assert len(stmts) == 2
    assert stmts[0].startswith("set")
    assert "keep=id" in stmts[0]


def test_balanced_parentheses_nested():
    text = "(where=(a in (1,2,3)) rename=(x=y)) tail"
    content, end = balanced_parentheses(text, 0)
    assert content == "(where=(a in (1,2,3)) rename=(x=y))"
    assert text[end:] == " tail"


def test_balanced_parentheses_quote_aware():
    content, _ = balanced_parentheses("(where=(s=');('))", 0)
    assert content == "(where=(s=');('))"


def test_balanced_parentheses_unbalanced_returns_none():
    assert balanced_parentheses("(keep=id", 0) is None
