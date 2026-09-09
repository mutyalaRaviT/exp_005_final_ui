"""Demo: parse a small SAS program and print blocks + edges.

DEV-ONLY: production spreadsheets come solely from the UI's /api/excel
verified merge — never from this script.
"""
from sas_lineage.graph import build_graph

SOURCE = """
/* stage raw data */
data work.customer;
    set raw.customer(keep=id name status);
run;

data work.customer_clean;
    set work.customer(where=(status="A"));
run;

data mart.customer;
    merge
        work.customer_clean
        raw.account(rename=(amt=amount));
    by id;
run;
"""


def main():
    blocks, edges = build_graph(SOURCE)

    print("== Blocks ==")
    for b in blocks:
        print(f"  {b.block_id}: {b.status}")
        for occ in [*b.reads, *b.writes]:
            print(f"      {occ.display}  ({occ.role})")
        if b.unresolved:
            print(f"      unresolved: {b.unresolved}")

    print("\n== Edges ==")
    for e in edges:
        print(f"  [{e.edge_type}] {e.display}")


if __name__ == "__main__":
    main()
