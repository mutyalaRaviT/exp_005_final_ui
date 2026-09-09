"""PROC SQL support via sqlglot.

Each statement inside `proc sql; ... quit;` is parsed with sqlglot:
  create table/view X as select ...  -> writes X, reads FROM/JOIN tables
  insert into X select ...           -> writes X, reads FROM/JOIN tables
  select ...                         -> reads only
Anything sqlglot cannot parse lands in `unresolved` (never dropped).
"""
import re

import sqlglot
from sqlglot import exp

from sas_lineage.models import TableRef

_SQL_HEADS = {"create", "insert", "select"}
_IGNORED_HEADS = {"quit", "run", "drop", "alter", "describe", "reset", "validate"}

# SAS SQL word operators that standard SQL parsers reject.
_SAS_WORD_OPS = {"eq": "=", "ne": "<>", "gt": ">", "lt": "<", "ge": ">=", "le": "<="}
_WORD = re.compile(r"[A-Za-z_]\w*|'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|\S")
_SQL_KEYWORDS = {
    "select", "from", "where", "group", "order", "having", "by", "on", "join",
    "inner", "left", "right", "full", "outer", "cross", "as", "and", "or",
    "not", "case", "when", "then", "else", "end", "union", "all", "distinct",
    "in", "is", "null", "between", "like", "exists", "limit",
}


# SAS column modifiers (select ... as x length=8 format=comma12.2 label='X')
# that standard SQL parsers reject. Values: numbers, formats (yymmdd10.,
# comma12.2, $8.), or quoted labels.
_COL_MODIFIER = re.compile(
    r"\s+(?:length|format|informat|label)\s*=\s*"
    r"(?:\$?\w+\.?\d*|'[^']*'|\"[^\"]*\")",
    re.IGNORECASE,
)
_QUOTED = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"")
# SAS missing-value literal used as a select operand: `select a, . from t`
_MISSING_LITERAL = re.compile(r"(?<=[,(\s])\.(?=\s*(?:,|\)|from\b|$))",
                              re.IGNORECASE)


def _rewrite_outside_quotes(statement: str, pattern: re.Pattern,
                            repl: str) -> str:
    """Apply pattern -> repl, quote-aware: string literals are masked (same
    length, quotes kept) so text inside them never matches, while match
    spans still map 1:1 onto the original text."""
    masked = _QUOTED.sub(
        lambda m: m.group(0)[0] + "#" * (len(m.group(0)) - 2) + m.group(0)[-1],
        statement)
    out, last = [], 0
    for m in pattern.finditer(masked):
        out.append(statement[last:m.start()])
        out.append(repl)
        last = m.end()
    out.append(statement[last:])
    return "".join(out)


def _strip_column_modifiers(statement: str) -> str:
    """Delete SAS-only column modifiers and rewrite the missing-value
    literal `.` to NULL, so sqlglot sees standard SQL."""
    statement = _rewrite_outside_quotes(statement, _COL_MODIFIER, "")
    return _rewrite_outside_quotes(statement, _MISSING_LITERAL, "NULL")


def _translate_sas_sql(statement: str) -> str:
    """Rewrite SAS word operators (a ne b -> a <> b) only when the word sits
    in operator position: between two operands, outside quotes. A column or
    table legitimately named `le`/`ne`/... is left alone, as are literals."""
    statement = _strip_column_modifiers(statement)
    out = statement
    offset = 0
    for m in _WORD.finditer(statement):
        word = m.group(0)
        lower = word.lower()
        if lower not in _SAS_WORD_OPS:
            continue  # quoted strings match as whole tokens, so ops inside them never get here
        prev_tok, next_tok = _neighbors(statement, m.start(), m.end())
        if prev_tok is None or next_tok is None:
            continue
        prev_is_operand = (prev_tok[-1].isalnum() or prev_tok[-1] in ")'\"._") \
            and prev_tok.lower() not in _SQL_KEYWORDS
        next_is_operand = (next_tok[0].isalnum() or next_tok[0] in "('\"._-") \
            and next_tok.lower() not in _SQL_KEYWORDS
        if prev_is_operand and next_is_operand:
            replacement = _SAS_WORD_OPS[lower]
            start, end = m.start() + offset, m.end() + offset
            out = out[:start] + replacement + out[end:]
            offset += len(replacement) - len(word)
    return out


def _neighbors(text: str, start: int, end: int):
    """The tokens immediately before and after [start, end), quote-aware."""
    before = _WORD.findall(text[:start])
    after = _WORD.findall(text[end:])
    return (before[-1] if before else None), (after[0] if after else None)


def _full_name(table: exp.Table) -> str:
    parts = [table.text("catalog"), table.text("db"), table.name]
    return ".".join(p for p in parts if p)


def _cte_names(tree) -> set[str]:
    return {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}


def _read_tables(select_part, skip: set[str]) -> list[TableRef]:
    refs, seen = [], set()
    if select_part is None:
        return refs
    for table in select_part.find_all(exp.Table):
        name = _full_name(table)
        if not name or name.lower() in skip or name.lower() in seen:
            continue
        seen.add(name.lower())
        refs.append(TableRef(name=name, raw=table.sql()))
    return refs


def parse_sql_statement(statement: str):
    """Return (reads, writes) or None if the statement is not lineage-relevant.
    Raises on SQL sqlglot cannot parse."""
    head = statement.split(None, 1)[0].lower() if statement.split() else ""
    if head in _IGNORED_HEADS or head not in _SQL_HEADS:
        return None
    tree = sqlglot.parse_one(_translate_sas_sql(statement))
    if isinstance(tree, exp.Command):
        # sqlglot could not truly parse it and fell back to a generic command;
        # treating that as "fine" would silently drop lineage.
        raise ValueError(f"unparseable SQL (Command fallback): {statement[:80]!r}")
    skip = _cte_names(tree)

    if isinstance(tree, (exp.Create, exp.Insert)):
        target = tree.this
        if isinstance(target, exp.Schema):
            target = target.this
        writes = [TableRef(name=_full_name(target), raw=target.sql())]
        reads = _read_tables(tree.expression, skip)
        return reads, writes
    if isinstance(tree, exp.Select):
        return _read_tables(tree, skip), []
    return None


def parse_proc_sql(statements: list[str]):
    """Parse a proc sql block's statements.

    Returns (reads, writes, unresolved, flows) where `flows` pairs each
    statement's reads with that statement's writes by canonical name — so a
    block holding several SQL statements never cross-products unrelated
    reads and writes.
    """
    reads, writes, unresolved, flows = [], [], [], []
    for stmt in statements[1:]:  # statements[0] is `proc sql ...`
        try:
            parsed = parse_sql_statement(stmt)
        except Exception:
            unresolved.append(stmt)
            continue
        if parsed is None:
            continue
        r, w = parsed
        reads.extend(r)
        writes.extend(w)
        flows.extend((read.canonical, write.canonical) for read in r for write in w)
    return reads, writes, unresolved, flows
