"""pipeline.tests.test_comments — proofs for pipeline/comments.py.

Unit-level proofs use synthetic token/statement dicts (no tokeniser or
swipl needed, fast). One integration-level proof runs the real Pig
tokeniser over pipeline/tests/fixtures/comments/inline_fallback.pig — the
purpose-built fixture for the "inline" fallback branch, since (per
code_graph/gold/string_escape_law_2026-08-26.md's sibling investigation)
that branch has ZERO occurrences anywhere in this project's real corpus
and cannot be proven against corpus data.
"""
from pathlib import Path

from pipeline.comments import extract_comments, attach_comments, render
from pipeline.run_fold import split_statements
from pipeline.tokeniser import tokenise
from pipeline.specs.pig import LANG as PIG_LANG

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "comments" / "inline_fallback.pig"


def _tok(kind, text, line, col=1):
    return {"kind": kind, "text": text, "line": line, "col": col, "b0": 0, "b1": 0}


def test_extract_comments_ignores_non_comment_tokens():
    tokens = [_tok("keyword", "LOAD", 1), _tok("comment", "-- a", 2), _tok("word", "x", 3)]
    got = extract_comments(tokens)
    assert got == [{"line": 2, "col": 1, "text": "-- a"}]


def test_extract_comments_splits_a_multiline_block_comment_per_physical_line():
    tokens = [_tok("comment", "/* line1\nline2\nline3 */", 5, col=3)]
    got = extract_comments(tokens)
    assert got == [
        {"line": 5, "col": 3, "text": "/* line1"},
        {"line": 6, "col": 1, "text": "line2"},
        {"line": 7, "col": 1, "text": "line3 */"},
    ]


def test_attach_leading_comment_goes_to_the_following_statement():
    stmts = [{"seq": 1, "l0": 3, "l1": 3}]
    comments = [{"line": 2, "col": 1, "text": "-- above stmt 1"}]
    got = attach_comments(comments, stmts)
    assert got == {1: [{"seq": 1, "pos": "leading", "line": 2, "text": "-- above stmt 1"}]}


def test_attach_trailing_comment_after_last_statement_line_stays_on_that_statement():
    stmts = [{"seq": 1, "l0": 1, "l1": 3}, {"seq": 2, "l0": 5, "l1": 5}]
    # sits ON stmt 1's last line (l1=3) -> trailing on seq 1, not leading on seq 2
    comments = [{"line": 3, "col": 40, "text": "-- trailing on stmt 1"}]
    got = attach_comments(comments, stmts)
    assert got == {1: [{"seq": 1, "pos": "trailing", "line": 3, "text": "-- trailing on stmt 1"}]}


def test_attach_comment_between_statements_prefers_the_following_one_on_a_tie():
    # stmt1 ends line 3, stmt2 starts line 5 -> comment on line 4 is
    # equidistant (1 line either way); ties go to the FOLLOWING statement.
    stmts = [{"seq": 1, "l0": 1, "l1": 3}, {"seq": 2, "l0": 5, "l1": 5}]
    comments = [{"line": 4, "col": 1, "text": "-- between, tied"}]
    got = attach_comments(comments, stmts)
    assert got == {2: [{"seq": 2, "pos": "leading", "line": 4, "text": "-- between, tied"}]}


def test_attach_comment_strictly_closer_to_before_goes_there():
    stmts = [{"seq": 1, "l0": 1, "l1": 1}, {"seq": 2, "l0": 10, "l1": 10}]
    comments = [{"line": 2, "col": 1, "text": "-- right after stmt 1"}]
    got = attach_comments(comments, stmts)
    assert got == {1: [{"seq": 1, "pos": "trailing", "line": 2, "text": "-- right after stmt 1"}]}


def test_attach_comment_after_the_last_statement_is_trailing_on_it():
    stmts = [{"seq": 1, "l0": 1, "l1": 1}]
    comments = [{"line": 5, "col": 1, "text": "-- footer"}]
    got = attach_comments(comments, stmts)
    assert got == {1: [{"seq": 1, "pos": "trailing", "line": 5, "text": "-- footer"}]}


def test_attach_comment_before_the_only_statement_is_leading_on_it():
    stmts = [{"seq": 1, "l0": 5, "l1": 5}]
    comments = [{"line": 1, "col": 1, "text": "-- header"}]
    got = attach_comments(comments, stmts)
    assert got == {1: [{"seq": 1, "pos": "leading", "line": 1, "text": "-- header"}]}


def test_attach_comment_in_a_file_with_zero_statements_is_the_prologue_bucket():
    comments = [{"line": 1, "col": 1, "text": "-- all alone"}]
    got = attach_comments(comments, [])
    assert got == {None: [{"seq": None, "pos": "prologue", "line": 1, "text": "-- all alone"}]}


def test_attach_inline_fallback_comment_inside_a_multiline_statement_not_on_its_last_line():
    # the owner's specifically-requested fallback: a comment strictly
    # BETWEEN a multi-line statement's first and last line.
    stmts = [{"seq": 1, "l0": 4, "l1": 8}]
    comments = [{"line": 6, "col": 5, "text": "-- buried mid-statement"}]
    got = attach_comments(comments, stmts)
    assert got == {1: [{"seq": 1, "pos": "inline", "line": 6, "text": "-- buried mid-statement"}]}


def test_render_format():
    att = {"seq": 1, "pos": "trailing", "line": 19, "text": "-- only gold-tier customers"}
    assert render(att, "p03.pig") == "# [p03.pig:19] -- only gold-tier customers"


def test_render_uses_the_given_comment_prefix():
    att = {"seq": 1, "pos": "leading", "line": 3, "text": "<!-- an oozie comment -->"}
    assert render(att, "w01.xml", comment_prefix="#") == "# [w01.xml:3] <!-- an oozie comment -->"


# ---- integration: the real Pig tokeniser, the purpose-built fixture ----

def test_inline_fallback_fixture_reaches_the_inline_branch_through_real_tokens():
    text = FIXTURE.read_text(encoding="utf-8")
    tokens = tokenise(PIG_LANG, text)
    stmts = split_statements(tokens)
    comments = extract_comments(tokens)
    attached = attach_comments(comments, stmts)

    assert [s["seq"] for s in stmts] == [1, 2]
    load_stmt = next(s for s in stmts if s["seq"] == 1)
    assert load_stmt["l0"] < 6 < load_stmt["l1"], "the comment must land strictly inside stmt 1's span"

    inline_hits = [a for a in attached[1] if a["pos"] == "inline"]
    assert len(inline_hits) == 3, "all 3 lines of the buried block comment are 'inline'"
    assert all(6 <= a["line"] <= 7 or a["line"] == 5 for a in inline_hits)

    leading_hits = [a for a in attached[1] if a["pos"] == "leading"]
    assert [a["line"] for a in leading_hits] == [1, 2], "the two header lines attach as leading on stmt 1"

    trailing_hits = attached[2]
    assert len(trailing_hits) == 1 and trailing_hits[0]["pos"] == "trailing"
    assert trailing_hits[0]["line"] == 10

    rendered = render(inline_hits[0], "inline_fallback.pig")
    assert rendered.startswith("# [inline_fallback.pig:5]")
