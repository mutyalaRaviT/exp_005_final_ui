"""Occurrence numbering, BLOCK_FLOW edges, and the FILE_FLOW second pass."""
from sas_lineage.blocks import scan_source
from sas_lineage.models import (
    BLOCK_FLOW,
    FILE_FLOW,
    NOT_MATCHED,
    BlockResult,
    Edge,
    TableOccurrence,
    TableRef,
)


def build_block_result(block_id, status, read_refs, write_refs, unresolved,
                       flows=None, kind="") -> BlockResult:
    """Number occurrences (reads first, then writes, in source order) and emit
    BLOCK_FLOW edges.

    flows=None: every read -> every write (a data step / single-statement proc).
    flows=[(read_canonical, write_canonical), ...]: only those pairs — used by
    multi-statement blocks (proc sql) so unrelated statements never connect.
    """
    result = BlockResult(block_id=block_id, status=status, kind=kind,
                         unresolved=list(unresolved))
    no = 0

    def occurrence(ref: TableRef, role: str) -> TableOccurrence:
        nonlocal no
        no += 1
        return TableOccurrence(
            id=f"{block_id}:t_{no}", name=ref.name,
            block_id=block_id, table_no=no, role=role,
        )

    result.reads = [occurrence(r, "read") for r in read_refs]
    result.writes = [occurrence(w, "write") for w in write_refs]

    if flows is None:
        result.edges = [
            Edge(r.display, w.display, BLOCK_FLOW)
            for r in result.reads
            for w in result.writes
        ]
    else:
        first_read = {}
        for r in result.reads:
            first_read.setdefault(r.canonical, r)
        first_write = {}
        for w in result.writes:
            first_write.setdefault(w.canonical, w)
        seen = set()
        result.edges = []
        for read_name, write_name in flows:
            r, w = first_read.get(read_name), first_write.get(write_name)
            if r and w and (r.display, w.display) not in seen:
                seen.add((r.display, w.display))
                result.edges.append(Edge(r.display, w.display, BLOCK_FLOW))
    return result


def file_flow_edges(blocks: list[BlockResult]) -> list[Edge]:
    """Second pass: latest earlier writer of a canonical name -> each later reader."""
    edges: list[Edge] = []
    latest_writer: dict[str, TableOccurrence] = {}
    for block in blocks:
        for read in block.reads:
            previous = latest_writer.get(read.canonical)
            if previous:
                edges.append(Edge(previous.display, read.display, FILE_FLOW))
        for write in block.writes:
            latest_writer[write.canonical] = write
    return edges


def _assemble(scans):
    blocks = [
        build_block_result(block_id, status, reads, writes, unresolved, flows, kind)
        for block_id, status, reads, writes, unresolved, flows, kind in scans
    ]
    lineage_blocks = [b for b in blocks if b.status != NOT_MATCHED]
    edges: list[Edge] = [e for b in lineage_blocks for e in b.edges]
    edges.extend(file_flow_edges(lineage_blocks))
    return blocks, edges


def build_graph(source: str):
    """Full pipeline over plain source (fallback b_<n>_<hash8> ids).
    Returns (block_results, all_edges)."""
    return _assemble(scan_source(source))


def build_graph_from_units(units):
    """Pipeline over pre-assembled units: (block_id, statements) pairs, in
    file order. Used when block ids come from BLOCKID annotations or from
    macro instantiation instead of the fallback b_<n>_<hash8> ids."""
    from sas_lineage.blocks import parse_block

    return _assemble(
        (block_id, *parse_block(block_id, statements))
        for block_id, statements in units
    )
