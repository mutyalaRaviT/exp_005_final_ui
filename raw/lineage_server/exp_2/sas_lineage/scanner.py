"""Tiny structural scanner for the pieces where regex is unsafe:
quoted strings, /* */ comments, semicolon boundaries, balanced parentheses.
"""

QUOTES = ("'", '"')


def strip_comments(text: str) -> str:
    """Remove /* ... */ comments, quote-aware."""
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in QUOTES:
            end = _skip_quote(text, i)
            out.append(text[i:end])
            i = end
        elif text.startswith("/*", i):
            close = text.find("*/", i + 2)
            i = n if close == -1 else close + 2
            out.append(" ")
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _skip_quote(text: str, start: int) -> int:
    """`start` is on a quote char; return index just past the closing quote."""
    q = text[start]
    i = start + 1
    while i < len(text):
        if text[i] == q:
            return i + 1
        i += 1
    return len(text)  # unterminated: consume to end


skip_quote = _skip_quote  # public alias for other layers


def find_statement_end(text: str, start: int = 0) -> int:
    """Index of the `;` ending the statement at `start` (quote-aware), or -1."""
    i = start
    while i < len(text):
        ch = text[i]
        if ch in QUOTES:
            i = _skip_quote(text, i)
        elif ch == ";":
            return i
        else:
            i += 1
    return -1


def split_statements(text: str) -> list[str]:
    """Split into `;`-terminated statements (the `;` is dropped), quote-aware."""
    statements = []
    i = 0
    while i < len(text):
        end = find_statement_end(text, i)
        if end == -1:
            tail = text[i:].strip()
            if tail:
                statements.append(tail)
            break
        stmt = text[i:end].strip()
        if stmt:
            statements.append(stmt)
        i = end + 1
    return statements


def balanced_parentheses(text: str, start: int):
    """`start` must be on '('. Return (content_span_text, end_pos_after_close) or None.

    Handles nesting and quoted strings; None if unbalanced.
    """
    if start >= len(text) or text[start] != "(":
        return None
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch in QUOTES:
            i = _skip_quote(text, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 1], i + 1
        i += 1
    return None
