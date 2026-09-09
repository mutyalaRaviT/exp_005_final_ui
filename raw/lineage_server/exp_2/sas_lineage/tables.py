"""TABLE_REF := TABLE_NAME + optional(BALANCED_DATASET_OPTIONS)
TABLE_LIST := one-or-more TABLE_REF

Dataset options are opaque: (keep=...), (where=(...)), (rename=(...)) are
skipped structurally, never parsed semantically.
"""
from sas_lineage.models import TableRef
from sas_lineage.regex_wrappers import match_table_name
from sas_lineage.scanner import QUOTES, balanced_parentheses, skip_quote


def parse_table_ref(text: str, pos: int = 0):
    """Parse one table ref at `pos`. Return (TableRef, end_pos) or None."""
    matched = match_table_name(text, pos)
    if not matched:
        return None
    name, end = matched
    # optional dataset options: an opaque balanced (...) region
    look = end
    while look < len(text) and text[look].isspace():
        look += 1
    if look < len(text) and text[look] == "(":
        balanced = balanced_parentheses(text, look)
        if balanced is None:
            return None  # unbalanced options — let the caller mark it unresolved
        _, end = balanced
    return TableRef(name=name, raw=text[pos:end]), end


def _skip_option_value(text: str, pos: int) -> int:
    """Skip the value of a `name=value` statement option: a quoted string,
    a balanced (...) region, or a bare word."""
    n = len(text)
    while pos < n and text[pos].isspace():
        pos += 1
    if pos < n and text[pos] == "(":
        balanced = balanced_parentheses(text, pos)
        return balanced[1] if balanced else n
    if pos < n and text[pos] in QUOTES:
        return skip_quote(text, pos)
    while pos < n and not text[pos].isspace() and text[pos] != "/":
        pos += 1
    return pos


def parse_table_list(text: str):
    """Parse one-or-more table refs. Return (refs, unresolved_fragments).

    Statement options are skipped structurally, not mistaken for tables:
    `name=value` pairs (end=, point=, nobs=, key=, ...) and everything after
    a top-level `/` (e.g. `data work.v / view=work.v`).
    """
    refs: list[TableRef] = []
    unresolved: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        if text[i] == "/":  # slash options: recognized, skipped
            break
        parsed = parse_table_ref(text, i)
        if parsed is None:
            unresolved.append(text[i:].strip())
            break
        ref, end = parsed
        look = end
        while look < n and text[look].isspace():
            look += 1
        if look < n and text[look] == "=":  # was an option name, not a table
            i = _skip_option_value(text, look + 1)
            continue
        refs.append(ref)
        i = end
    return refs, unresolved
