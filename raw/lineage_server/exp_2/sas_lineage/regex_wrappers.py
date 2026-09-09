"""Lexical layer only: identifiers, table names, keywords. No nesting, no `.*`."""
import re

IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
TABLE_NAME = rf"{IDENTIFIER}(?:\.{IDENTIFIER})?"

_IDENTIFIER_RE = re.compile(IDENTIFIER)
_TABLE_NAME_RE = re.compile(TABLE_NAME)


def match_identifier(text: str, pos: int = 0):
    """Return (identifier, end_pos) or None."""
    m = _IDENTIFIER_RE.match(text, pos)
    return (m.group(0), m.end()) if m else None


def match_table_name(text: str, pos: int = 0):
    """Return (table_name, end_pos) or None. Matches `libref.member` or bare name."""
    m = _TABLE_NAME_RE.match(text, pos)
    return (m.group(0), m.end()) if m else None


def is_keyword(statement: str, keyword: str) -> bool:
    """True if `statement` starts with `keyword` (case-insensitive, word-bounded)."""
    return bool(
        re.match(rf"\s*{re.escape(keyword)}(?![A-Za-z0-9_])", statement, re.IGNORECASE)
    )


def strip_keyword(statement: str, keyword: str) -> str | None:
    """Remove a leading keyword; None if the statement does not start with it."""
    m = re.match(rf"\s*{re.escape(keyword)}(?![A-Za-z0-9_])", statement, re.IGNORECASE)
    return statement[m.end():].strip() if m else None
