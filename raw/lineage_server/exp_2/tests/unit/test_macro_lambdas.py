from pathlib import Path

from sas_lineage.macro_lambdas import MacroLambda, find_step_calls, is_step_macro
from sas_lineage.macros import MacroDef
from sas_lineage.models import FILE_FLOW
from sas_lineage.pipeline import analyze_file, analyze_source

EXAMPLES = Path(__file__).resolve().parent.parent.parent / "examples"

STAGE = MacroDef("stage", ["src", "dst"],
                 "data &dst.;\n    set &src.;\nrun;")


def test_is_step_macro():
    assert is_step_macro(STAGE)
    assert is_step_macro(MacroDef("q", [], "proc sql;\nselect 1;\nquit;"))
    assert not is_step_macro(MacroDef("frag", ["t"], "raw.&t."))  # expression


def test_lambda_generates_edges_for_given_tables():
    lam = MacroLambda(STAGE, "m_stage")
    edges = lam("raw.cust", "work.cust")
    assert [e.display for e in edges] == [
        "m_stage#1:t_1_raw.cust -> m_stage#1:t_2_work.cust"
    ]


def test_lambda_keyword_args_and_instances():
    lam = MacroLambda(STAGE, "m_stage")
    edges = lam(src="raw.a", dst="work.a", instance=3)
    assert [e.display for e in edges] == [
        "m_stage#3:t_1_raw.a -> m_stage#3:t_2_work.a"
    ]


def test_lambda_uses_annotated_definition_block_id():
    lam = MacroLambda(STAGE, "1:5550001112223334")
    edges = lam("raw.x", "work.x")
    assert edges[0].display == (
        "1:5550001112223334#1:t_1_raw.x -> 1:5550001112223334#1:t_2_work.x"
    )


def test_find_step_calls_splits_text():
    parts = find_step_calls(
        "data a; set b; run;\n%stage(raw.x, work.x);\ndata c; set work.x; run;",
        {"stage": STAGE},
    )
    kinds = [p[0] for p in parts]
    assert kinds == ["text", "call", "text"]
    assert parts[1][1] == "stage"
    assert parts[1][2] == ["raw.x", "work.x"]


def test_pipeline_two_calls_get_instances():
    analysis = analyze_file(EXAMPLES / "ex11_annotated_macro.sas",
                            registry_path=None)
    ids = [b.block_id for b in analysis.blocks]
    assert ids == [
        "1:5550001112223334#1", "1:5550001112223334#2", "4:8880004445556667",
    ]
    assert [(c.name, c.instance, c.call_block_id, c.def_block_id)
            for c in analysis.macro_calls] == [
        ("stage_table", 1, "2:6660002223334445", "1:5550001112223334"),
        ("stage_table", 2, "3:7770003334445556", "1:5550001112223334"),
    ]


def test_pipeline_file_edges_link_macro_and_caller_blocks():
    analysis = analyze_file(EXAMPLES / "ex11_annotated_macro.sas",
                            registry_path=None)
    file_flow = [e.display for e in analysis.edges if e.edge_type == FILE_FLOW]
    # macro-definition-derived ids on one side, caller's injected id on the other
    assert file_flow == [
        "1:5550001112223334#1:t_2_work.customers_stg -> 4:8880004445556667:t_1_work.customers_stg",
        "1:5550001112223334#2:t_2_work.accounts_stg -> 4:8880004445556667:t_2_work.accounts_stg",
    ]


def test_analysis_exposes_lambdas():
    analysis = analyze_source(
        "%macro cp(s, d);\ndata &d.;\n set &s.;\nrun;\n%mend;\n"
        "data work.o;\n set raw.i;\nrun;"
    )
    lam = analysis.lambdas["cp"]
    edges = lam("raw.n", "work.n")
    assert [e.display for e in edges] == ["m_cp#1:t_1_raw.n -> m_cp#1:t_2_work.n"]


def test_expression_macro_still_inlined():
    src = (
        "%macro tbl(t);raw.&t.%mend;\n"
        "data work.o;\n set %tbl(cust);\nrun;"
    )
    analysis = analyze_source(src)
    assert analysis.blocks[0].status == "PARSED"
    assert [o.name for o in analysis.blocks[0].reads] == ["raw.cust"]
