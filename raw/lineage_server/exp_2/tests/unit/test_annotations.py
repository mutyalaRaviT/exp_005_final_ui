from pathlib import Path

from sas_lineage.annotations import split_annotated
from sas_lineage.models import FILE_FLOW
from sas_lineage.pipeline import analyze_file, analyze_source

EXAMPLES = Path(__file__).resolve().parent.parent.parent / "examples"

ANNOTATED = """/*Analyzed: 08/24/2026 11:33:17
Complexity: 3 285.19 LoC: 24
Errors: 0 in 0/2 Blocks
*/

/*BLOCKID 1:2645661869534515, Proc SQL, Lines: 23 - 7 to 30 : 100%;*/
PROC SQL;
CREATE TABLE work.rollup AS SELECT id FROM work.base;
;
run;
/*ENDBLOCKID 1:2645661869534515, Proc SQL;*/
"""


def test_split_annotated_extracts_id_and_meta():
    segments = split_annotated(ANNOTATED)
    annotated = [s for s in segments if s.block_id]
    assert len(annotated) == 1
    assert annotated[0].block_id == "1:2645661869534515"
    assert annotated[0].meta.startswith("Proc SQL")
    assert "CREATE TABLE" in annotated[0].text


def test_file_header_comment_is_not_a_block():
    segments = split_annotated(ANNOTATED)
    # the /*Analyzed ...*/ header sits in an un-annotated segment
    assert segments[0].block_id is None
    assert "Analyzed" in segments[0].text


def test_annotated_id_becomes_block_id():
    analysis = analyze_source(ANNOTATED)
    parsed = [b for b in analysis.blocks if b.status == "PARSED"]
    assert [b.block_id for b in parsed] == ["1:2645661869534515"]
    assert parsed[0].reads[0].id == "1:2645661869534515:t_1"


def test_unannotated_code_keeps_fallback_ids(plain):
    analysis = analyze_source("data work.x;\n set raw.y;\nrun;")
    block_id = analysis.blocks[0].block_id
    assert plain(block_id) == "b_1"
    assert block_id.startswith("b_1_") and len(block_id.split("_")[2]) == 8


def test_mixed_annotated_and_plain(plain):
    src = ANNOTATED + "\ndata work.extra;\n set work.rollup;\nrun;"
    analysis = analyze_source(src)
    ids = [plain(b.block_id) for b in analysis.blocks if b.status == "PARSED"]
    assert ids == ["1:2645661869534515", "b_1"]
    file_flow = [plain(e.display) for e in analysis.edges
                 if e.edge_type == FILE_FLOW]
    assert file_flow == [
        "1:2645661869534515:t_2_work.rollup -> b_1:t_1_work.rollup"
    ]


def test_two_steps_inside_one_annotation_get_suffixes():
    src = """/*BLOCKID 9:111, Multi, Lines: 1;*/
data work.a;
 set raw.x;
run;
data work.b;
 set work.a;
run;
/*ENDBLOCKID 9:111, Multi;*/"""
    analysis = analyze_source(src)
    assert [b.block_id for b in analysis.blocks] == ["9:111", "9:111.2"]


def test_ex10_end_to_end():
    analysis = analyze_file(EXAMPLES / "ex10_annotated_blocks.sas",
                            registry_path=None)
    assert [b.block_id for b in analysis.blocks] == [
        "1:2645661869534515", "2:7118293441055627",
    ]
    assert all(b.status == "PARSED" for b in analysis.blocks)
    displays = [e.display for e in analysis.edges]
    assert ("1:2645661869534515:t_4_work.branch_rollup -> "
            "2:7118293441055627:t_1_work.branch_rollup") in displays
