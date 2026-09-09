"""pipeline.tests.test_codegen_common_comments — proofs for
pipeline.codegen.common's comment_lines/with_trailing (2026-08-26),
the two helpers every codegen module uses to turn a node4 record's
"comments" list into generated-code lines."""
from pipeline.codegen.common import comment_lines, with_trailing


def _att(pos, line, text):
    return {"seq": 1, "pos": pos, "line": line, "text": text}


def test_comment_lines_includes_only_leading_and_prologue_by_default():
    atts = [
        _att("leading", 1, "-- header"),
        _att("trailing", 5, "-- trailing, excluded here"),
        _att("inline", 3, "-- inline, excluded here"),
    ]
    got = comment_lines(atts, "p.pig")
    assert got == ["# [p.pig:1] -- header"]


def test_comment_lines_applies_indent_to_every_line():
    atts = [_att("leading", 1, "-- a"), _att("leading", 2, "-- b")]
    got = comment_lines(atts, "p.pig", indent="    ")
    assert got == ["    # [p.pig:1] -- a", "    # [p.pig:2] -- b"]


def test_with_trailing_appends_a_single_trailing_comment():
    atts = [_att("trailing", 7, "-- only gold-tier customers")]
    got = with_trailing('gold_txn = txn.filter(F.col("tier") == "gold")', atts, "p.pig")
    assert got == 'gold_txn = txn.filter(F.col("tier") == "gold")  # [p.pig:7] -- only gold-tier customers'


def test_with_trailing_appends_multiple_inline_comments_in_source_order():
    atts = [_att("inline", 5, "-- first"), _att("inline", 6, "-- second")]
    got = with_trailing("x = 1", atts, "p.pig")
    assert got == "x = 1  # [p.pig:5] -- first  # [p.pig:6] -- second"


def test_with_trailing_returns_the_line_unchanged_when_no_trailing_or_inline_comments():
    atts = [_att("leading", 1, "-- only leading, not appended here")]
    got = with_trailing("x = 1", atts, "p.pig")
    assert got == "x = 1"


def test_with_trailing_on_an_empty_attachment_list_is_a_no_op():
    assert with_trailing("x = 1", [], "p.pig") == "x = 1"
