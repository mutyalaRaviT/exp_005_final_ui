"""Regression tests for the 2026-08-24 code-review findings. One test per
confirmed finding, in review order."""
from pathlib import Path

from sas_lineage.pipeline import analyze_source
from sas_lineage.sql import _translate_sas_sql, parse_sql_statement


# 1. SAS word operators must only be rewritten in operator position
def test_sql_word_op_column_named_le_survives():
    reads, writes = parse_sql_statement(
        "create table work.t2 as select le, id from raw.limits")
    assert [r.name for r in reads] == ["raw.limits"]
    assert [w.name for w in writes] == ["work.t2"]


def test_sql_word_op_literal_survives():
    translated = _translate_sas_sql("select id from raw.a where state_cd = 'NE'")
    assert "'NE'" in translated


def test_sql_word_op_in_operator_position_rewritten():
    assert "a <> b" in _translate_sas_sql("select id from t where a ne b")
    assert "amt >= 10" in _translate_sas_sql("select id from t where amt ge 10")


# 2. a macro call inside a comment is not a call, and must not eat real code
def test_macro_call_in_comment_is_ignored():
    src = (
        "%macro stage(s, d);\ndata &d.;\n set &s.;\nrun;\n%mend;\n"
        "/* old approach: %stage(raw.a, work.a); no longer used */\n"
        "data work.z;\n set raw.z;\nrun;\n"
    )
    analysis = analyze_source(src)
    names = [(o.name for o in b.writes) for b in analysis.blocks]
    writes = [o.name for b in analysis.blocks for o in b.writes]
    assert writes == ["work.z"]          # no phantom work.a
    assert analysis.macro_calls == []    # the commented call never fired
    assert analysis.blocks[0].status == "PARSED"


# 3. a step macro calling another step macro keeps the nested lineage
def test_nested_step_macro_lineage_kept():
    src = (
        "%macro inner(s, d);\ndata &d.;\n set &s.;\nrun;\n%mend;\n"
        "%macro outer(x);\n"
        "data work.pre_&x.;\n set raw.&x.;\nrun;\n"
        "%inner(work.pre_&x., work.final_&x.);\n"
        "%mend;\n"
        "%outer(cust);\n"
    )
    analysis = analyze_source(src)
    pairs = {
        (e.source.split("_", 10)[-1], e.target)  # crude but names are unique here
        for e in analysis.edges
    }
    all_writes = [o.name for b in analysis.blocks for o in b.writes]
    assert "work.pre_cust" in all_writes
    assert "work.final_cust" in all_writes   # nested macro's write survived
    assert len(analysis.edges) == 3          # 2 BLOCK_FLOW + 1 FILE_FLOW


# 6. two step macros in one annotated span get distinct instance block ids
def test_two_macros_in_one_annotation_distinct_ids():
    src = """/*BLOCKID 1:999, Macros, Lines: 1;*/
%macro a(s);
data work.out_a;
 set &s.;
run;
%mend;
%macro b(s);
data work.out_b;
 set &s.;
run;
%mend;
/*ENDBLOCKID 1:999, Macros;*/
%a(raw.x);
%b(raw.y);
"""
    analysis = analyze_source(src)
    ids = [b.block_id for b in analysis.blocks]
    assert len(ids) == len(set(ids)), ids
    assert ids == ["1:999.a#1", "1:999.b#1"]
