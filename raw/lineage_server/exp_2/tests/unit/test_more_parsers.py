"""Extra edge-case coverage across every layer."""
import pytest

from sas_lineage.graph import build_graph
from sas_lineage.macros import expand
from sas_lineage.models import BLOCK_FLOW, FILE_FLOW
from sas_lineage.pipeline import analyze_source, extract_libnames
from sas_lineage.scanner import split_statements, strip_comments
from sas_lineage.sql import parse_sql_statement
from sas_lineage.tables import parse_table_list


# ---- scanner ----------------------------------------------------------------

def test_unterminated_comment_swallows_to_end():
    assert strip_comments("data a; /* never closed").strip() == "data a;"


def test_mixed_quote_types():
    stmts = split_statements("x = \"it's; fine\"; y = 'say \"hi\"; ok';")
    assert len(stmts) == 2


def test_comment_between_statements_with_quotes():
    text = strip_comments("set a; /* 'quoted ; comment' */ set b;")
    assert "comment" not in text
    assert "set a;" in text and "set b;" in text


# ---- tables -----------------------------------------------------------------

def test_numbered_and_underscored_names():
    refs, unresolved = parse_table_list("lib2.tab_3 _tmp raw._x9")
    assert [r.name for r in refs] == ["lib2.tab_3", "_tmp", "raw._x9"]
    assert unresolved == []


def test_option_value_quoted():
    refs, unresolved = parse_table_list("raw.a indsname='who knows'")
    assert [r.name for r in refs] == ["raw.a"]
    assert unresolved == []


def test_option_value_parenthesised():
    refs, unresolved = parse_table_list("raw.a keys=(id name) raw.b")
    assert [r.name for r in refs] == ["raw.a", "raw.b"]
    assert unresolved == []


def test_three_level_name_is_not_silently_accepted():
    refs, unresolved = parse_table_list("a.b.c")
    # a.b parses as the ref; the dangling `.c` must surface, not vanish
    assert [r.name for r in refs] == ["a.b"]
    assert unresolved == [".c"]


# ---- macros -----------------------------------------------------------------

def test_macro_calling_macro():
    src = (
        "%macro inner(t);\nset raw.&t.;\n%mend;\n"
        "%macro outer(t);\ndata work.&t.;\n%inner(&t.)\nrun;\n%mend;\n"
        "%outer(cust);\n"
    )
    expanded, _, _ = expand(src)
    assert "data work.cust;" in expanded
    assert "set raw.cust;" in expanded


def test_macro_without_parens_call():
    src = "%macro fixed;\ndata work.a;\n set raw.a;\nrun;\n%mend;\n%fixed;\n"
    expanded, _, _ = expand(src)
    assert "set raw.a;" in expanded


def test_let_chained_resolution():
    src = "%let env = prod;\n%let lib = raw_&env.;\ndata w.x;\n set &lib..t;\nrun;"
    expanded, _, _ = expand(src)
    assert "set raw_prod.t;" in expanded


def test_macro_case_insensitive_invocation():
    src = "%macro CP(s);\ndata work.o;\n set &S.;\nrun;\n%mend;\n%cp(raw.in);\n"
    expanded, _, _ = expand(src)
    assert "set raw.in;" in expanded


def test_recursive_macro_does_not_hang():
    src = "%macro loop;\n%loop\n%mend;\n%loop\n"
    expanded, _, _ = expand(src)  # backstop must terminate the expansion
    assert isinstance(expanded, str)


# ---- sql --------------------------------------------------------------------

def test_create_view():
    reads, writes = parse_sql_statement(
        "create view work.v as select id from raw.base"
    )
    assert [r.name for r in reads] == ["raw.base"]
    assert [w.name for w in writes] == ["work.v"]


def test_union_reads_both_sides():
    reads, _ = parse_sql_statement(
        "create table work.u as select id from raw.a union all select id from raw.b"
    )
    assert sorted(r.name for r in reads) == ["raw.a", "raw.b"]


def test_three_way_join():
    reads, _ = parse_sql_statement(
        "create table work.j as select a.id from raw.a as a "
        "join raw.b as b on a.id=b.id left join raw.c as c on b.id=c.id"
    )
    assert sorted(r.name for r in reads) == ["raw.a", "raw.b", "raw.c"]


def test_duplicate_reads_deduped_within_statement():
    reads, _ = parse_sql_statement(
        "create table work.s as select a.id from raw.a as a "
        "join raw.a as a2 on a.id = a2.id"
    )
    assert [r.name for r in reads] == ["raw.a"]


def test_drop_statement_ignored():
    src = "proc sql;\n drop table work.old;\n create table work.n as select id from raw.a;\nquit;"
    blocks, edges = build_graph(src)
    assert blocks[0].status == "PARSED"
    assert len([e for e in edges if e.edge_type == BLOCK_FLOW]) == 1


# ---- procs / blocks ---------------------------------------------------------

def test_proc_sort_with_dataset_options(plain):
    _, edges = build_graph(
        "proc sort data=raw.x(where=(ok=1)) out=work.y(drop=tmp);\n by id;\nrun;"
    )
    assert [plain(e.display) for e in edges] == ["b_1:t_1_raw.x -> b_1:t_2_work.y"]


def test_proc_append_new_alias(plain):
    _, edges = build_graph("proc append base=work.all new=work.delta;\nrun;")
    assert [plain(e.display) for e in edges] == [
        "b_1:t_1_work.delta -> b_1:t_2_work.all"]


def test_proc_transpose_missing_out_is_loud():
    blocks, edges = build_graph("proc transpose data=work.x;\nrun;")
    assert blocks[0].status == "NOT_MATCHED"
    assert edges == []


def test_unclosed_data_step_still_parses():
    blocks, _ = build_graph("data work.x;\n set raw.y;")  # no run;
    assert blocks[0].status == "PARSED"


def test_two_sql_blocks_chain_via_file_flow(plain):
    src = (
        "proc sql;\n create table work.a as select id from raw.x;\nquit;\n"
        "proc sql;\n create table work.b as select id from work.a;\nquit;"
    )
    _, edges = build_graph(src)
    file_flow = [plain(e.display) for e in edges if e.edge_type == FILE_FLOW]
    assert file_flow == ["b_1:t_2_work.a -> b_2:t_1_work.a"]


# ---- libnames ---------------------------------------------------------------

def test_extract_libnames_both_quote_styles():
    libs = extract_libnames(
        "libname raw '/data/raw';\nlibname mart \"/data/mart\";"
    )
    assert libs == {"raw": "/data/raw", "mart": "/data/mart"}


def test_libname_case_insensitive_and_last_wins():
    libs = extract_libnames("LIBNAME Raw '/a';\nlibname raw '/b';")
    assert libs == {"raw": "/b"}


def test_libname_from_macro_variable():
    analysis = analyze_source(
        "%let root = /data;\nlibname raw \"&root./raw\";\n"
        "data work.x;\n set raw.y;\nrun;"
    )
    assert analysis.libnames == {"raw": "/data/raw"}
