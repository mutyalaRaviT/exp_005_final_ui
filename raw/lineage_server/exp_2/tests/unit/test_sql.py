from sas_lineage.graph import build_graph
from sas_lineage.models import BLOCK_FLOW, FILE_FLOW
from sas_lineage.sql import parse_sql_statement


def test_create_as_select_with_join():
    reads, writes = parse_sql_statement(
        "create table work.co as select c.id, o.amt from raw.cust as c "
        "inner join raw.ord as o on c.id = o.cid"
    )
    assert sorted(r.name for r in reads) == ["raw.cust", "raw.ord"]
    assert [w.name for w in writes] == ["work.co"]


def test_insert_select():
    reads, writes = parse_sql_statement(
        "insert into work.log select id from work.co"
    )
    assert [r.name for r in reads] == ["work.co"]
    assert [w.name for w in writes] == ["work.log"]


def test_plain_select_is_read_only():
    reads, writes = parse_sql_statement("select count(*) from work.co")
    assert [r.name for r in reads] == ["work.co"]
    assert writes == []


def test_cte_names_are_not_reads():
    reads, _ = parse_sql_statement(
        "create table work.x as with recent as "
        "(select * from raw.events where ts > 5) select * from recent"
    )
    assert [r.name for r in reads] == ["raw.events"]


def test_proc_sql_block_no_cross_statement_edges(plain):
    src = """proc sql;
    create table work.co as
    select c.id from raw.cust as c inner join raw.ord as o on c.id = o.cid;

    insert into work.audit select id, 'x' from work.co;

    select count(*) from work.co;
quit;"""
    blocks, edges = build_graph(src)
    block_flow = [plain(e.display) for e in edges if e.edge_type == BLOCK_FLOW]
    assert "b_1:t_1_raw.cust -> b_1:t_5_work.co" in block_flow
    assert "b_1:t_2_raw.ord -> b_1:t_5_work.co" in block_flow
    assert "b_1:t_3_work.co -> b_1:t_6_work.audit" in block_flow
    # the false cross-product edge must NOT exist:
    assert not any(e.startswith("b_1:t_1_raw.cust -> b_1:t_6") for e in block_flow)
    assert len(block_flow) == 3


def test_unparseable_sql_is_partial_not_silent():
    src = "proc sql;\n create table work.x as select from from where;\nquit;"
    blocks, _ = build_graph(src)
    assert blocks[0].status in ("PARTIAL", "NOT_MATCHED")
    assert blocks[0].unresolved


def test_sql_feeds_file_flow_to_later_data_step(plain):
    src = """proc sql;
    create table work.co as select id from raw.cust;
quit;

data work.final;
    set work.co;
run;"""
    _, edges = build_graph(src)
    file_flow = [plain(e.display) for e in edges if e.edge_type == FILE_FLOW]
    assert file_flow == ["b_1:t_2_work.co -> b_2:t_1_work.co"]


def test_sas_length_modifier_in_select_is_stripped():
    stmt = ("create table work.risk_flags as select c.cust_id, "
            "case when c.risk_score >= 0.75 then 'HIGH' else 'LOW' end "
            "as risk_band length=8 from work.cust_summary c")
    reads, writes = parse_sql_statement(stmt)
    assert [w.name for w in writes] == ["work.risk_flags"]
    assert [r.name for r in reads] == ["work.cust_summary"]


def test_sas_format_and_label_modifiers_stripped():
    stmt = ("create table work.t as select 'BRANCH' as metric_type length=12, "
            "amt format=comma12.2, open_dt format=yymmdd10., "
            "nm label='Customer Name' from work.src")
    reads, writes = parse_sql_statement(stmt)
    assert [w.name for w in writes] == ["work.t"]
    assert [r.name for r in reads] == ["work.src"]


def test_length_inside_string_literal_untouched():
    stmt = "create table work.t as select 'length=99' as tag from work.src"
    reads, writes = parse_sql_statement(stmt)
    assert [r.name for r in reads] == ["work.src"]


def test_missing_value_literal_becomes_null():
    stmt = ("create table work.t as select 'X' as a, . from work.src "
            "union all select 'Y', b from work.other")
    reads, writes = parse_sql_statement(stmt)
    assert [w.name for w in writes] == ["work.t"]
    assert {r.name for r in reads} == {"work.src", "work.other"}


def test_dot_inside_string_and_numbers_untouched():
    stmt = ("create table work.t as select 'v1.2' as tag, amt * 0.75 as x "
            "from work.src")
    reads, _ = parse_sql_statement(stmt)
    assert [r.name for r in reads] == ["work.src"]
