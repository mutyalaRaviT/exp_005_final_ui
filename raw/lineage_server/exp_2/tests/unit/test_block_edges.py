from sas_lineage.graph import build_graph
from sas_lineage.models import BLOCK_FLOW


def test_occurrence_numbering_reads_first_then_writes(plain):
    blocks, _ = build_graph("data work.final;\n merge raw.a raw.b;\nrun;")
    b = blocks[0]
    assert [plain(o.display) for o in b.reads] == ["b_1:t_1_raw.a",
                                                   "b_1:t_2_raw.b"]
    assert [plain(o.display) for o in b.writes] == ["b_1:t_3_work.final"]


def test_block_flow_cross_product(plain):
    _, edges = build_graph("data work.x work.y;\n set raw.z;\nrun;")
    assert [plain(e.display) for e in edges if e.edge_type == BLOCK_FLOW] == [
        "b_1:t_1_raw.z -> b_1:t_2_work.x",
        "b_1:t_1_raw.z -> b_1:t_3_work.y",
    ]


def test_block_ids_are_deterministic(plain):
    src = "data a;\n set r.x;\nrun;\ndata b;\n set r.y;\nrun;"
    blocks, _ = build_graph(src)
    assert [plain(b.block_id) for b in blocks] == ["b_1", "b_2"]
    # same source, same run -> byte-identical ids
    again, _ = build_graph(src)
    assert [b.block_id for b in blocks] == [b.block_id for b in again]


def test_fallback_block_id_carries_an_8_char_content_hash():
    blocks, _ = build_graph("data w.a;\n set r.a;\nrun;")
    block_id = blocks[0].block_id
    assert block_id.startswith("b_1_")
    assert len(block_id.split("_")[2]) == 8


def test_block_id_constant_when_block_unchanged():
    src1 = "data w.a; set r.a; run;\ndata w.b; set r.b; run;"
    src2 = "data w.a; set r.a; run;\ndata w.b; set r.b r.c; run;"
    ids1 = [b.block_id for b in build_graph(src1)[0]]
    ids2 = [b.block_id for b in build_graph(src2)[0]]
    assert ids1[0] == ids2[0]   # untouched block: same id
    assert ids1[1] != ids2[1]   # edited block: new hash
    assert ids1[0].startswith("b_1_") and len(ids1[0].split("_")[2]) == 8


def test_blocks_carry_their_step_kind():
    from sas_lineage.graph import build_graph
    blocks, _ = build_graph(
        "data work.a; set raw.x; run;\n"
        "proc sql; create table work.b as select * from work.a; quit;\n"
        "proc sort data=work.b out=work.c; by k; run;\n"
        "proc unknownthing; run;")
    assert [b.kind for b in blocks] == ["data", "proc sql", "proc sort",
                                       "proc unknownthing"]
