"""Statement-driven block splitting and per-block parsing.

A block runs from a `data` or `proc` statement to its `run`/`quit` statement.
Fallback block ids are deterministic AND content-addressed:
`b_<ordinal>_<hash8>` (b_1_1234abcd, b_2_...). The ordinal is positional;
the hash is of the block's own statements, so a block whose text is untouched
keeps its id when the rest of the file changes — and human notes pinned to
that id survive. Injected /*BLOCKID*/ ids and macro instance ids (`<id>#k`)
are unaffected; the hash only applies to these fallback ids.

Dispatch:  data ...      -> DATA-step parser (set/merge/update/modify)
           proc sql ...  -> sqlglot-based SQL parser
           proc sort/append/transpose -> dedicated PROC parsers
           other procs   -> NOT_MATCHED (loud, never silent)
"""
import hashlib
import re

from sas_lineage.data_step import READ_PARSERS, parse_data_header
from sas_lineage.models import NOT_MATCHED, PARSED, PARTIAL, TableRef
from sas_lineage.procs import PROC_PARSERS
from sas_lineage.scanner import split_statements, strip_comments
from sas_lineage.sql import parse_proc_sql

_STEP_HEADS = {"data", "proc"}
_END_HEADS = {"run", "quit"}


def block_hash(statements: list[str]) -> str:
    """8 hex chars over the block's own statements — the block's fingerprint."""
    return hashlib.sha1("".join(statements).encode()).hexdigest()[:8]


def fallback_block_id(ordinal: int, statements: list[str]) -> str:
    """`b_<ordinal>_<hash8>`: position keeps the id readable, the content hash
    keeps it stable while the block's text is untouched."""
    return f"b_{ordinal}_{block_hash(statements)}"


def _head(statement: str) -> str:
    parts = statement.split(None, 1)
    return parts[0].lower() if parts else ""


def split_blocks(source: str) -> list[list[str]]:
    """Return blocks as lists of statements (comments stripped)."""
    statements = split_statements(strip_comments(source))
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for stmt in statements:
        head = _head(stmt)
        if head in _STEP_HEADS:
            if current:  # previous step never closed by run/quit
                blocks.append(current)
            current = [stmt]
        elif current is not None:
            current.append(stmt)
            if head in _END_HEADS:
                blocks.append(current)
                current = None
    if current:
        blocks.append(current)
    return blocks


# statements that positively identify a step sourcing data inline, not
# from another table
_INLINE_SOURCE_HEADS = {"datalines", "cards", "datalines4", "cards4",
                        "infile", "input"}
# statements that cannot introduce a table read
_NON_READ_HEADS = {
    "length", "format", "informat", "label", "attrib", "retain", "keep",
    "drop", "rename", "output", "run", "put", "call", "array", "by",
    "where", "stop", "return", "delete", "file", "do", "end", "else",
    "select", "when", "otherwise",
}
_READ_KEYWORD = re.compile(r"\b(set|merge|update|modify)\b", re.IGNORECASE)
_ASSIGNMENT = re.compile(r"[A-Za-z_]\w*\s*(?:\([^)]*\))?\s*=")


def _is_sourceless(statements: list[str]) -> bool:
    """True when a data step with no matched read statement is positively a
    source-less writer (seed data / pure assignments) rather than a step
    whose read syntax we failed to recognize."""
    body = statements[1:]
    # a read keyword we did not parse means we must stay NOT_MATCHED
    if any(_READ_KEYWORD.search(s) for s in body):
        return False
    heads = [_head(s) for s in body]
    if any(h in _INLINE_SOURCE_HEADS for h in heads):
        return True
    return all(h in _NON_READ_HEADS or h == "if" or _ASSIGNMENT.match(s)
               for h, s in zip(heads, body))


def _parse_data_step(statements: list[str]):
    reads: list[TableRef] = []
    writes: list[TableRef] = []
    unresolved: list[str] = []

    refs, bad = parse_data_header(statements[0])
    # data _null_ writes nothing: valid step, no write occurrences
    writes.extend(r for r in refs if r.name.lower() != "_null_")
    unresolved.extend(bad)

    matched_read = False
    for stmt in statements[1:]:
        for parser in READ_PARSERS:
            result = parser(stmt)
            if result is not None:
                refs, bad = result
                reads.extend(refs)
                unresolved.extend(bad)
                matched_read = True
                break

    if not matched_read and not _is_sourceless(statements):
        return NOT_MATCHED, reads, writes, unresolved, None
    status = PARTIAL if unresolved else PARSED
    return status, reads, writes, unresolved, None


def parse_block(block_id: str, statements: list[str]):
    """Return (status, read_refs, write_refs, unresolved, flows, kind)."""
    first = statements[0]
    head = _head(first)

    if head == "data":
        return (*_parse_data_step(statements), "data")

    if head == "proc":
        m = re.match(r"\s*proc\s+([A-Za-z_]\w*)", first, re.IGNORECASE)
        proc_name = m.group(1).lower() if m else ""
        kind = f"proc {proc_name}" if proc_name else "proc"
        if proc_name == "sql":
            reads, writes, unresolved, flows = parse_proc_sql(statements)
            if not reads and not writes:
                return NOT_MATCHED, [], [], unresolved, None, kind
            return (PARTIAL if unresolved else PARSED), reads, writes, unresolved, flows, kind
        if proc_name in PROC_PARSERS:
            reads, writes, unresolved = PROC_PARSERS[proc_name](statements)
            if not reads and not writes:
                return NOT_MATCHED, [], [], unresolved, None, kind
            return (PARTIAL if unresolved else PARSED), reads, writes, unresolved, None, kind
        return NOT_MATCHED, [], [], [], None, kind

    return NOT_MATCHED, [], [], [], None, ""


def scan_source(source: str):
    """Yield (block_id, status, read_refs, write_refs, unresolved, flows, kind).

    `flows` is None for cross-product blocks (data steps, single-statement
    procs) or explicit (read_canonical, write_canonical) pairs for blocks
    holding several independent statements (proc sql).
    graph.py turns these raw TableRefs into occurrences and edges.
    """
    for i, statements in enumerate(split_blocks(source), start=1):
        block_id = fallback_block_id(i, statements)
        yield (block_id, *parse_block(block_id, statements))
