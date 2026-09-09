"""PROC step parsers (non-SQL). Each reuses `table_ref` — table syntax is
never re-implemented here. All return (read_refs, write_refs, unresolved).
"""
import re

from sas_lineage.models import TableRef
from sas_lineage.tables import parse_table_ref


def option_table(text: str, option: str) -> TableRef | None:
    """Extract `option=<table_ref>` from a statement (case-insensitive)."""
    m = re.search(rf"\b{re.escape(option)}\s*=\s*", text, re.IGNORECASE)
    if not m:
        return None
    parsed = parse_table_ref(text, m.end())
    return parsed[0] if parsed else None


def parse_proc_sort(statements: list[str]):
    """proc sort data=in out=out;  — no out= means an in-place sort
    (the table is both read and written)."""
    head = statements[0]
    data = option_table(head, "data")
    out = option_table(head, "out")
    if data is None:
        return [], [], [head]
    return [data], [out or data], []


def parse_proc_append(statements: list[str]):
    """proc append base=target data=source;  (`new=` is an alias of data=)."""
    head = statements[0]
    base = option_table(head, "base")
    data = option_table(head, "data") or option_table(head, "new")
    if base is None or data is None:
        return [], [], [head]
    return [data], [base], []


def parse_proc_transpose(statements: list[str]):
    """proc transpose data=in out=out;  by/var/id statements are ignored."""
    head = statements[0]
    data = option_table(head, "data")
    out = option_table(head, "out")
    if data is None or out is None:
        return [], [], [head]
    return [data], [out], []


PROC_PARSERS = {
    "sort": parse_proc_sort,
    "append": parse_proc_append,
    "transpose": parse_proc_transpose,
}
