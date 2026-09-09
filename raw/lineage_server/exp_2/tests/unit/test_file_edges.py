from sas_lineage.graph import build_graph
from sas_lineage.models import BLOCK_FLOW, FILE_FLOW


def test_three_block_chain_alternates_block_and_file_flow(plain):
    src = """data work.customer;
    set raw.customer;
run;

data work.customer_clean;
    set work.customer;
run;

data mart.customer;
    set work.customer_clean;
run;"""
    _, edges = build_graph(src)
    displayed = [(e.edge_type, plain(e.display)) for e in edges]
    assert (BLOCK_FLOW, "b_1:t_1_raw.customer -> b_1:t_2_work.customer") in displayed
    assert (FILE_FLOW, "b_1:t_2_work.customer -> b_2:t_1_work.customer") in displayed
    assert (BLOCK_FLOW, "b_2:t_1_work.customer -> b_2:t_2_work.customer_clean") in displayed
    assert (
        FILE_FLOW,
        "b_2:t_2_work.customer_clean -> b_3:t_1_work.customer_clean",
    ) in displayed
    assert (BLOCK_FLOW, "b_3:t_1_work.customer_clean -> b_3:t_2_mart.customer") in displayed
    assert len(displayed) == 5


def test_file_flow_uses_latest_writer(plain):
    src = (
        "data work.a;\n set raw.x;\nrun;\n"
        "data work.a;\n set raw.y;\nrun;\n"  # overwrites work.a
        "data work.b;\n set work.a;\nrun;"
    )
    _, edges = build_graph(src)
    file_flow = [plain(e.display) for e in edges if e.edge_type == FILE_FLOW]
    assert file_flow == ["b_2:t_2_work.a -> b_3:t_1_work.a"]


def test_file_flow_matching_is_case_insensitive(plain):
    src = "data WORK.A;\n set raw.x;\nrun;\ndata work.b;\n set work.a;\nrun;"
    _, edges = build_graph(src)
    file_flow = [plain(e.display) for e in edges if e.edge_type == FILE_FLOW]
    assert file_flow == ["b_1:t_2_WORK.A -> b_2:t_1_work.a"]
