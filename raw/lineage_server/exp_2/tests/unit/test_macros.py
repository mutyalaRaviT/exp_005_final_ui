from sas_lineage.macros import (
    MacroDef,
    expand,
    extract_lets,
    extract_macros,
)
from sas_lineage.pipeline import analyze_source


def test_extract_macro_definition():
    src = "%macro load(month, mart=work);\nselect &month.;\n%mend load;\ndata a; set b; run;"
    remaining, macros = extract_macros(src)
    assert "load" in macros
    assert macros["load"].params == ["month", "mart"]
    assert "select &month.;" in macros["load"].body
    assert "%macro" not in remaining


def test_extract_lets():
    remaining, variables = extract_lets("%let lib = raw;\ndata a; set &lib..x; run;")
    assert variables == {"lib": "raw"}
    assert "%let" not in remaining


def test_expand_positional_and_keyword_args():
    src = (
        "%macro cp(src, dst=work.out);\n"
        "data &dst.;\n    set &src.;\nrun;\n"
        "%mend;\n"
        "%cp(raw.a);\n"
        "%cp(raw.b, dst=work.b2);\n"
    )
    expanded, defs, _ = expand(src)
    assert "set raw.a;" in expanded
    assert "data work.b2;" in expanded
    assert "cp" in defs
    assert "%cp" not in expanded


def test_let_dot_terminator():
    expanded, _, _ = expand("%let lib = raw;\ndata w.x;\n set &lib..cust;\nrun;")
    assert "set raw.cust;" in expanded


def test_registry_macros_injectable():
    known = {"stage": MacroDef("stage", ["t"], "data work.&t.;\n set raw.&t.;\nrun;")}
    expanded, _, _ = expand("%stage(cust);", extra_macros=known)
    assert "set raw.cust;" in expanded


def test_macro_wrapped_sql_end_to_end():
    src = """%let src_lib = raw;
%macro load_cust(month, mart=work);
proc sql;
    create table &mart..cust_&month. as
    select c.id from &src_lib..customer as c
    left join &src_lib..region as r on c.rid = r.id;
quit;
%mend;
%load_cust(jan);
"""
    analysis = analyze_source(src)
    b = analysis.blocks[0]
    assert b.status == "PARSED"
    assert sorted(o.name for o in b.reads) == ["raw.customer", "raw.region"]
    assert [o.name for o in b.writes] == ["work.cust_jan"]


def test_unresolved_macro_var_is_partial_not_silent():
    analysis = analyze_source("data work.x;\n set &undefined_lib..cust;\nrun;")
    assert analysis.blocks[0].status == "PARTIAL"
    assert analysis.blocks[0].unresolved
