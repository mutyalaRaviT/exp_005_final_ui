from sas_lineage.graph import build_graph
from sas_lineage.tables import parse_table_list


def names(refs):
    return [r.name for r in refs]


def test_set_options_are_not_tables():
    refs, unresolved = parse_table_list("raw.a end=last point=_n_ nobs=total")
    assert names(refs) == ["raw.a"]
    assert unresolved == []


def test_slash_options_are_skipped():
    refs, unresolved = parse_table_list("work.v / view=work.v")
    assert names(refs) == ["work.v"]
    assert unresolved == []


def test_data_null_writes_nothing_but_reads_count():
    blocks, edges = build_graph("data _null_;\n set work.summary end=done;\nrun;")
    b = blocks[0]
    assert b.status == "PARSED"
    assert [o.name for o in b.reads] == ["work.summary"]
    assert b.writes == []
    assert edges == []


def test_proc_sort_with_out(plain):
    blocks, edges = build_graph(
        "proc sort data=raw.events out=work.sorted;\n by id;\nrun;"
    )
    assert blocks[0].status == "PARSED"
    assert [plain(e.display) for e in edges] == [
        "b_1:t_1_raw.events -> b_1:t_2_work.sorted"]


def test_proc_sort_in_place():
    blocks, _ = build_graph("proc sort data=work.x;\n by id;\nrun;")
    b = blocks[0]
    assert [o.name for o in b.reads] == ["work.x"]
    assert [o.name for o in b.writes] == ["work.x"]


def test_proc_append(plain):
    _, edges = build_graph("proc append base=work.hist data=work.new;\nrun;")
    assert [plain(e.display) for e in edges] == [
        "b_1:t_1_work.new -> b_1:t_2_work.hist"]


def test_proc_transpose(plain):
    _, edges = build_graph(
        "proc transpose data=work.long out=work.wide;\n by id;\nrun;"
    )
    assert [plain(e.display) for e in edges] == [
        "b_1:t_1_work.long -> b_1:t_2_work.wide"]


def test_unknown_proc_is_loudly_not_matched():
    blocks, edges = build_graph("proc means data=work.x;\nrun;")
    assert blocks[0].status == "NOT_MATCHED"
    assert edges == []
