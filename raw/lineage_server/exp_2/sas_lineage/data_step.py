"""Statement parsers. `parse` does the structural capture; `table_list` does all
table syntax — no statement parser re-implements it.
"""
import parse

from sas_lineage.regex_wrappers import strip_keyword
from sas_lineage.tables import parse_table_list

_CAPTURE = parse.compile("{keyword} {rest}")


def _capture(keyword: str, statement: str):
    """Case-insensitive keyword match + `parse`-style capture of the remainder."""
    rest = strip_keyword(statement, keyword)
    if rest is None:
        return None
    result = _CAPTURE.parse(f"{keyword} {rest}")
    return result["rest"] if result else None


def _tables_after(keyword: str, statement: str):
    rest = _capture(keyword, statement)
    if rest is None:
        return None
    return parse_table_list(rest)


def parse_data_header(statement: str):
    """`data work.x work.y;` -> writes. None if not a data statement."""
    return _tables_after("data", statement)


def parse_set(statement: str):
    return _tables_after("set", statement)


def parse_merge(statement: str):
    return _tables_after("merge", statement)


def parse_update(statement: str):
    return _tables_after("update", statement)


def parse_modify(statement: str):
    return _tables_after("modify", statement)


READ_PARSERS = (parse_set, parse_merge, parse_update, parse_modify)
