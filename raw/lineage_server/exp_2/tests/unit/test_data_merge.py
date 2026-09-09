from sas_lineage.data_step import parse_merge, parse_update
from sas_lineage.graph import build_graph


def test_parse_merge_statement():
    refs, unresolved = parse_merge("merge raw.a(keep=id) raw.b")
    assert [r.name for r in refs] == ["raw.a", "raw.b"]
    assert unresolved == []


def test_parse_update_statement():
    refs, _ = parse_update("update master.tx new.tx")
    assert [r.name for r in refs] == ["master.tx", "new.tx"]


def test_merge_block_with_options_and_by(plain):
    src = """data work.final;
    merge
        raw.customer(
            keep=id amount
        )
        raw.account(
            where=(status="A")
            rename=(amt=amount)
        );

    by id;
run;"""
    blocks, edges = build_graph(src)
    assert [plain(e.display) for e in edges] == [
        "b_1:t_1_raw.customer -> b_1:t_3_work.final",
        "b_1:t_2_raw.account -> b_1:t_3_work.final",
    ]
    assert blocks[0].status == "PARSED"
