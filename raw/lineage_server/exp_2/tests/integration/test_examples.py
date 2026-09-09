"""End-to-end checks over the complex example files in examples/."""
from pathlib import Path

import pytest

from sas_lineage.models import BLOCK_FLOW, FILE_FLOW
from sas_lineage.pipeline import analyze_file

EXAMPLES = Path(__file__).resolve().parent.parent.parent / "examples"


def logical(analysis, edge_type=BLOCK_FLOW):
    """Edges as lowercase (source_table, target_table) name pairs."""
    names = {
        o.display: o.canonical
        for b in analysis.blocks
        for o in [*b.reads, *b.writes]
    }
    return {
        (names[e.source], names[e.target])
        for e in analysis.edges
        if e.edge_type == edge_type
    }


def analyze(name):
    return analyze_file(EXAMPLES / name, registry_path=None)


def test_ex1_multi_set_options():
    a = analyze("ex1_multi_set_options.sas")
    assert [b.status for b in a.blocks] == ["PARSED"]
    assert logical(a) == {
        ("raw.txn_2025", "work.combined"), ("raw.txn_2025", "work.rejects"),
        ("raw.txn_2026", "work.combined"), ("raw.txn_2026", "work.rejects"),
        ("raw.adjustments", "work.combined"), ("raw.adjustments", "work.rejects"),
    }
    read_names = [o.name for b in a.blocks for o in b.reads]
    assert "end" not in read_names and "point" not in read_names


def test_ex2_merge_in_flags():
    a = analyze("ex2_merge_in_flags.sas")
    assert [b.status for b in a.blocks] == ["PARSED"]
    assert logical(a) == {
        ("work.customers", "work.matched"),
        ("work.orders", "work.matched"),
    }


def test_ex3_null_and_view():
    a = analyze("ex3_null_and_view.sas")
    assert [b.status for b in a.blocks] == ["PARSED", "PARSED"]
    null_block = a.blocks[0]
    assert null_block.writes == []
    assert [o.name for o in null_block.reads] == ["work.summary"]
    assert logical(a) == {("work.customers", "work.v_active")}


def test_ex4_proc_sort_append(plain):
    a = analyze("ex4_proc_sort_append.sas")
    assert [b.status for b in a.blocks] == ["PARSED"] * 3
    assert logical(a) == {
        ("raw.events", "work.events_sorted"),
        ("work.events_sorted", "work.events_sorted"),  # in-place sort
        ("work.events_sorted", "work.event_history"),  # append
    }
    # sorted output flows into the later blocks: b_1 -> b_2 and b_2 -> b_3
    file_flow = [plain(e.display) for e in a.edges if e.edge_type == FILE_FLOW]
    assert file_flow == [
        "b_1:t_2_work.events_sorted -> b_2:t_1_work.events_sorted",
        "b_2:t_2_work.events_sorted -> b_3:t_1_work.events_sorted",
    ]


def test_ex5_transpose_update():
    a = analyze("ex5_transpose_update.sas")
    assert [b.status for b in a.blocks] == ["PARSED", "PARSED"]
    assert logical(a) == {
        ("work.metrics_long", "work.metrics_wide"),
        ("work.metrics_wide", "work.master"),
        ("work.master", "work.master"),  # update reads and rewrites master
    }
    assert logical(a, FILE_FLOW) == {("work.metrics_wide", "work.metrics_wide")}


def test_ex6_arrays_do_loops():
    a = analyze("ex6_arrays_do_loops.sas")
    assert [b.status for b in a.blocks] == ["PARSED"]
    assert logical(a) == {("work.scores_raw", "work.scores_clean")}


def test_ex7_proc_sql():
    a = analyze("ex7_proc_sql.sas")
    assert [b.status for b in a.blocks] == ["PARSED"]
    assert logical(a) == {
        ("raw.customers", "work.cust_orders"),
        ("raw.orders", "work.cust_orders"),
        ("work.cust_orders", "work.audit_log"),
    }


def test_ex8_macro_sql():
    a = analyze("ex8_macro_sql.sas")
    assert "load_customers" in a.macros
    assert a.let_vars == {"src_lib": "raw"}
    assert [b.status for b in a.blocks] == ["PARSED", "PARSED"]
    assert logical(a) == {
        ("raw.customer", "work.cust_jan"),
        ("raw.region", "work.cust_jan"),
        ("work.cust_jan", "work.cust_jan_active"),
    }
    assert logical(a, FILE_FLOW) == {("work.cust_jan", "work.cust_jan")}
