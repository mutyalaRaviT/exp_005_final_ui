"""pipeline.term_parse — Prolog term text -> plain Python data.

Why this file exists: out/ir/<lang>/<stem>.node4.json's "term" field is a
Prolog term written as text by driver.pl's writeq (e.g.
`assign(rel(b),filter(rel(a),gt(col(v),lit(15))))`). Codegen (Phase D)
needs that text as ordinary Python data to walk and dispatch on. This is
a small, dumb recursive-descent reader for exactly the term shapes the
fold harness prints — not a general Prolog reader (no operators, no
variables, no comments inside terms).

Mapping from Prolog syntax to Python values:
    functor(arg1, arg2, ...)   -> tuple ("functor", arg1, arg2, ...)
    bareatom                   -> str "bareatom"          (0-arity atom)
    'quoted atom'               -> str, decoded per SWI-Prolog's plain
                                    writeq/2 escaping (2026-08-26 fix — see
                                    below), NOT the '' quote-doubling this
                                    docstring used to claim
    [a, b, c]                   -> list [a, b, c]  (Python list, recurses)
    123 / -5 / 3.14 / 1.0e-3    -> int or float

TERM-READABILITY LAW (2026-08-26): driver.pl (pipeline/prolog/driver.pl)
writes every folded/2 and printed/2 term with PLAIN writeq/2 — not
escape_pl_atom/2 (that predicate exists only to write the printed/2 TEXT
LIST, a different fact, never the term itself). This module's job is to
read back exactly what writeq/2 produced, and until 2026-08-26 it did not:
it only unescaped '' quote-doubling, while writeq/2 actually escapes an
embedded quote as \' and an embedded backslash as \\ (standard C-style
backslash escaping, verified empirically against a live swipl: an atom
whose value contains a literal backslash-then-quote comes back from
writeq/2 as 'it\\\'s', never as 'it''s'). Any atom value containing a
literal backslash or quote — the exact shape a REGISTER path or a Pig
string with an escaped apostrophe produces — used to raise
TermParseError("expected ',' or ')' at offset N") deep inside codegen,
with no file/block/seq to point at. pipeline.run_fold now also asserts
this readability at fold time (the TERM-READABILITY LAW check in
process_file) so a future regression here fails loudly, immediately,
with context — not as a bare offset three pipeline stages later.

A compound term with zero arguments never occurs in this corpus's output
(driver.pl only ever prints `foo` for a 0-arity atom, never `foo()`), so
a bare atom is always just a Python str, never a 1-tuple.
"""


class TermParseError(ValueError):
    """Malformed or trailing-garbage term text."""


# SWI-Prolog writeq/2's standard backslash escapes for a quoted atom,
# verified empirically (see term_parse's module docstring, 2026-08-26 fix)
# via a live swipl: writeq('a<TAB>b<NL>c\<DQ>d') -> 'a\tb\nc\\"d'. A double
# quote is NOT escaped inside a single-quoted atom (it isn't the delimiter),
# so it is absent from this map on purpose — a bare '"' in the text is
# already correct and needs no decoding.
_BACKSLASH_ESCAPES = {
    "\\": "\\", "'": "'", "`": "`",
    "a": "\a", "b": "\b", "f": "\f", "n": "\n",
    "r": "\r", "t": "\t", "v": "\v",
}


SYMBOL_ATOM_CHARS = set("+-*/\\^<>=~:.?@#&$")   # exp_42 2026-09-07: Prolog symbol-char atoms


def parse_term(text):
    """Parse exactly one Prolog term from `text` and return its Python
    representation. Raises TermParseError if `text` is not a single
    well-formed term (including trailing content after the term)."""
    p = _Parser(text)
    p._skip_ws()
    term = p._parse_term()
    p._skip_ws()
    if p.pos != len(p.text):
        raise TermParseError(
            f"trailing content at offset {p.pos}: {p.text[p.pos:p.pos + 30]!r}"
        )
    return term


class _Parser:
    def __init__(self, text):
        self.text = text
        self.pos = 0

    def _peek(self):
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def _skip_ws(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def _parse_term(self):
        self._skip_ws()
        ch = self._peek()
        if ch == "":
            raise TermParseError("unexpected end of input while parsing a term")
        if ch == "[":
            return self._parse_list()
        if ch == "'":
            atom = self._parse_quoted_atom()
            return self._maybe_compound(atom)
        if ch.isdigit() or (ch == "-" and self.text[self.pos + 1:self.pos + 2].isdigit()):
            return self._parse_number()
        if ch.isalpha() or ch == "_":
            atom = self._parse_bare_atom()
            return self._maybe_compound(atom)
        if ch in SYMBOL_ATOM_CHARS:
            # exp_42 (2026-09-07): writeq prints an atom made only of symbol
            # characters bare — lit(*) for PySpark's select("*"), or `<=`.
            start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] in SYMBOL_ATOM_CHARS:
                self.pos += 1
            return self._maybe_compound(self.text[start:self.pos])
        raise TermParseError(f"unexpected character {ch!r} at offset {self.pos}")

    def _maybe_compound(self, functor):
        # No whitespace is permitted between a functor and its '(' in
        # canonical writeq output, so we check the very next character
        # without skipping whitespace first.
        if self.pos < len(self.text) and self.text[self.pos] == "(":
            self.pos += 1
            args = self._parse_arglist(")")
            return (functor,) + tuple(args)
        return functor

    def _parse_arglist(self, close_ch):
        args = []
        self._skip_ws()
        if self._peek() == close_ch:
            self.pos += 1
            return args
        while True:
            args.append(self._parse_term())
            self._skip_ws()
            ch = self._peek()
            if ch == ",":
                self.pos += 1
                self._skip_ws()
                continue
            if ch == close_ch:
                self.pos += 1
                break
            raise TermParseError(
                f"expected ',' or {close_ch!r} at offset {self.pos}: "
                f"{self.text[self.pos:self.pos + 20]!r}"
            )
        return args

    def _parse_list(self):
        assert self._peek() == "["
        self.pos += 1
        return self._parse_arglist("]")

    def _parse_quoted_atom(self):
        assert self._peek() == "'"
        self.pos += 1
        out = []
        while True:
            if self.pos >= len(self.text):
                raise TermParseError("unterminated quoted atom")
            ch = self.text[self.pos]
            if ch == "\\":
                if self.pos + 1 >= len(self.text):
                    raise TermParseError("trailing backslash in quoted atom")
                nxt = self.text[self.pos + 1]
                if nxt in _BACKSLASH_ESCAPES:
                    out.append(_BACKSLASH_ESCAPES[nxt])
                    self.pos += 2
                    continue
                if nxt == "\n":
                    # writeq's line-continuation escape: backslash-newline
                    # contributes no character at all (a soft line break
                    # inside the source of a quoted atom, not part of its
                    # value) -- unlikely from this pipeline's own writeq
                    # calls but legal input, handled rather than mis-read.
                    self.pos += 2
                    continue
                raise TermParseError(
                    f"unrecognised backslash escape '\\{nxt}' at offset {self.pos}"
                )
            if ch == "'":
                # '' quote-doubling: not what THIS pipeline's writeq/2
                # produces (verified — it uses \' instead, see module
                # docstring), but still legal ISO Prolog quoting, kept for
                # robustness against any other term-writing path.
                if self.pos + 1 < len(self.text) and self.text[self.pos + 1] == "'":
                    out.append("'")
                    self.pos += 2
                    continue
                self.pos += 1
                break
            out.append(ch)
            self.pos += 1
        return "".join(out)

    def _parse_bare_atom(self):
        start = self.pos
        while self.pos < len(self.text) and (
            self.text[self.pos].isalnum() or self.text[self.pos] == "_"
        ):
            self.pos += 1
        return self.text[start:self.pos]

    def _parse_number(self):
        start = self.pos
        if self._peek() == "-":
            self.pos += 1
        while self.pos < len(self.text) and self.text[self.pos].isdigit():
            self.pos += 1
        is_float = False
        if self._peek() == "." and self.pos + 1 < len(self.text) and self.text[self.pos + 1].isdigit():
            is_float = True
            self.pos += 1
            while self.pos < len(self.text) and self.text[self.pos].isdigit():
                self.pos += 1
        if self._peek() in ("e", "E"):
            look = self.pos + 1
            if look < len(self.text) and (self.text[look] in "+-" or self.text[look].isdigit()):
                is_float = True
                self.pos = look
                if self._peek() in "+-":
                    self.pos += 1
                while self.pos < len(self.text) and self.text[self.pos].isdigit():
                    self.pos += 1
        num_text = self.text[start:self.pos]
        return float(num_text) if is_float else int(num_text)
