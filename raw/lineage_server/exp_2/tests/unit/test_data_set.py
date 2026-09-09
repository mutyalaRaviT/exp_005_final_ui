"""The five core tests from the spec (section 10), on logical lineage."""
from sas_lineage.graph import build_graph


def logical_edges(source):
    """BLOCK_FLOW edges as (read_name -> write_name) strings."""
    blocks, edges = build_graph(source)
    names = {
        occ.display: occ.name
        for b in blocks
        for occ in [*b.reads, *b.writes]
    }
    return sorted(
        f"{names[e.source]} -> {names[e.target]}"
        for e in edges
        if e.edge_type == "BLOCK_FLOW"
    )


def test_1_single_set():
    assert logical_edges("data work.x;\n set raw.y;\nrun;") == ["raw.y -> work.x"]


def test_2_two_sources():
    assert logical_edges("data work.x;\n set raw.y raw.z;\nrun;") == [
        "raw.y -> work.x",
        "raw.z -> work.x",
    ]


def test_3_two_targets():
    assert logical_edges("data work.x work.y;\n set raw.z;\nrun;") == [
        "raw.z -> work.x",
        "raw.z -> work.y",
    ]


def test_4_dataset_options():
    src = "data work.x;\n set raw.y(\n keep=id name\n );\nrun;"
    assert logical_edges(src) == ["raw.y -> work.x"]


def test_5_nested_options_two_sources():
    src = (
        "data work.x;\n"
        "    set\n"
        "        raw.y(\n            where=(a in (1,2,3))\n        )\n"
        "        raw.z(\n            rename=(x=y)\n        );\n"
        "run;"
    )
    assert logical_edges(src) == ["raw.y -> work.x", "raw.z -> work.x"]


def test_status_partial_on_unresolved():
    blocks, _ = build_graph("data work.x;\n set raw.y &mac;\nrun;")
    assert blocks[0].status == "PARTIAL"
    assert blocks[0].unresolved == ["&mac"]


def test_assignment_only_step_is_sourceless_writer():
    # a step of pure assignments legitimately reads nothing (e.g. audit logs)
    blocks, edges = build_graph("data work.x;\n y = 10;\nrun;")
    assert blocks[0].status == "PARSED"
    assert [w.canonical for w in blocks[0].writes] == ["work.x"]
    assert blocks[0].reads == []
    assert edges == []


def test_datalines_step_is_sourceless_writer():
    src = (
        "data work.customers;\n"
        "  length cust_id $8;\n"
        "  infile datalines dsd dlm='|' truncover;\n"
        "  input cust_id;\n"
        "datalines;\nC001\nC002\n;\nrun;"
    )
    blocks, _ = build_graph(src)
    assert blocks[0].status == "PARSED"
    assert [w.canonical for w in blocks[0].writes] == ["work.customers"]
    assert blocks[0].reads == []


def test_unknown_statement_still_not_matched():
    # an unrecognized statement may hide a read — stay loud, not silent
    blocks, _ = build_graph("data work.x;\n frobnicate raw.y;\nrun;")
    assert blocks[0].status == "NOT_MATCHED"


def test_mentioned_read_keyword_in_unparsed_statement_not_matched():
    # `set` appears but no parser matched it: never claim a clean parse
    blocks, _ = build_graph("data work.x;\n if flag then set raw.y;\nrun;")
    assert blocks[0].status == "NOT_MATCHED"
