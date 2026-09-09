"""pydsl_lib — the few constructors behind expr_pydsl.py.

Why: one expression grammar, written once, read by people and by two
generators (Rustemo and Prolog DCG). This file only builds plain data;
gen.py turns it into grammars.

Vocabulary (same words as docs1 step_5_expr_ladder where it has them):
  ladder(level, level, ...)   tightest-binding level FIRST, loosest last
  level(name, ops, assoc)     one precedence level; name is the term functor
                              family, ops come from one_of/prefix, assoc is
                              "left" | "right" | "none" (no chaining)
  one_of(op, ...)             infix operator spellings; a dict maps spelling
                              -> term functor when they differ
  prefix(op, ...)             unary prefix operator spellings
  list_rhs(op)                infix op whose right side is "( e, e, ... )"
  leaf(name, ...)             a token that is itself an expression
  form(name, shape)           a fixed shape such as "( E )" or "if E then E else E"
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union


@dataclass
class Op:
    spelling: str          # what the source text says: "+", "and", "^="
    functor: str           # the term it builds: add, and, ne
    kind: str = "infix"    # infix | prefix | list_rhs


def _ops(kind: str, *spellings, functor: Union[str, Dict[str, str], None]):
    out = []
    for s in spellings:
        if isinstance(functor, dict):
            f = functor[s]
        elif functor is None:
            f = s
        else:
            f = functor
        out.append(Op(s, f, kind))
    return out


def one_of(*spellings, functor=None):
    return _ops("infix", *spellings, functor=functor)


def prefix(*spellings, functor=None):
    return _ops("prefix", *spellings, functor=functor)


def list_rhs(*spellings, functor=None):
    return _ops("list_rhs", *spellings, functor=functor)


@dataclass
class Level:
    name: str
    ops: List[Op]
    assoc: str = "left"          # left | right | none; ignored for prefix
    rhs: Optional[str] = None    # right operand may come from this (looser) level
    doc: str = ""

    @property
    def is_prefix(self):
        return all(o.kind == "prefix" for o in self.ops)


def level(name, ops, assoc="left", rhs=None, doc=""):
    return Level(name, ops, assoc, rhs, doc)


def ladder(*levels):
    return list(levels)


@dataclass
class Leaf:
    name: str        # token and functor family: number, string, ident, ...
    pattern: str     # regex, Rustemo dialect (also documents the shape)
    term: str        # how the term is written, with {v} for the token text
    doc: str = ""
    dequote: bool = False  # exp_014: this leaf's token text still carries
                            # its surrounding quote characters and needs
                            # dequoting before building the term. Only the
                            # "string" and "atom" leaf NAMES are ever
                            # dequoted (gen_prolog.py's LEAF_PARSE/LEAF_PRINT
                            # dispatch on name) — pipeline/gen_prolog.py's
                            # generate() checks this at generate time
                            # (2026-08-26) and sys.exits on any OTHER leaf
                            # name that sets dequote=True, since that flag
                            # would otherwise be silently ignored.
    double_delim: bool = False  # exp_014 (2026-08-26): does this leaf's own
                            # tokeniser regex accept a DOUBLED delimiter
                            # character (''/"") as an in-string escape for
                            # one literal delimiter char, on top of the
                            # universal backslash-escape (\X -> X) every
                            # quoted leaf's regex already allows? Hive's
                            # string_single/string_double leaves do
                            # (`'(?:\\.|''|[^'\\])*'`); Pig/Sqoop/Oozie's
                            # quoted leaves do not — for them a bare `''`
                            # in source is never one token to begin with
                            # (their regex has no `''` alternative, so the
                            # tokeniser closes the string at the first
                            # quote and a second, empty string token
                            # follows). Only meaningful when dequote=True.


    backslash_escape: bool = True  # exp_42 (2026-09-05): SAS strings have NO
                            # backslash escape ('C:\\SASData' is four real
                            # characters). False = only the doubled delimiter
                            # is an escape; gen_prolog then uses
                            # unquote_plain/quote_plain instead of
                            # unquote_escaped/quote_escaped.


def leaf(name, pattern, term, doc="", dequote=False, double_delim=False, backslash_escape=True):
    return Leaf(name, pattern, term, doc, dequote, double_delim, backslash_escape)


@dataclass
class Form:
    name: str        # functor
    shape: str       # words: E = any expression, ARGS = "e, e, ...", ID/MFN = a token, others literal
    doc: str = ""


def form(name, shape, doc=""):
    return Form(name, shape, doc)


@dataclass
class Grammar:
    language: str
    leaves: List[Leaf]
    ladder: List[Level]
    forms: List[Form]
    keywords_case_insensitive: bool = True


def expression_grammar(language, leaves, ladder, forms, keywords_case_insensitive=True):
    return Grammar(language, leaves, ladder, forms, keywords_case_insensitive)


# ---------------------------------------------------------------------------
# Statement vocabulary (exp_014 phase C). Same discipline as everything
# above: a handful of plain-data pieces, written once per language in
# pipeline/specs/<lang>.py, turned into a DCG by pipeline/gen_prolog.py.
# `ladder`/`level`/`one_of`/`prefix`/`leaf`/`form` above ARE the expression
# half of a statement grammar — `expr(field)` below just hooks into them.
# A statement's `parts` is a straight-line sequence, source order, of the
# pieces below. KW/SYM match literal tokens and contribute no term argument;
# every other piece contributes exactly one term argument, in order.

@dataclass
class KW:
    """One keyword token, matched case-insensitively; canonical print
    spelling is `text` lowercased. e.g. kw("FOREACH")."""
    text: str


@dataclass
class SYM:
    """One symbol token, matched (and printed) by exact spelling `text`,
    e.g. sym("("), sym("::")."""
    text: str


@dataclass
class Cap:
    """One captured argument. kind="ref": a WORD token -> rel(Atom), a
    relation alias. kind="ident": a WORD token -> bare Atom (a schema
    field/type name, not a relation). kind="typename": a WORD OR KEYWORD
    token -> bare Atom — for a name-position slot whose usual spellings
    happen to collide with the language's own keyword list (Hive's schema
    column types INT/DOUBLE/STRING are also entries in hive.py's
    `keywords`, so they tokenise as kind=keyword, not kind=word; plain
    `ident` would never match them). Deliberately narrower than widening
    `ident` itself: broadening EVERY ident() site to accept keyword-kind
    tokens would let an optional trailing alias (e.g. a FROM table alias)
    greedily swallow a following real keyword like WHERE during parse
    backtracking — safe in principle (full-consumption backtracking would
    still find the right parse) but needlessly multiplies the search
    space at every alias site for a collision that only ever happens at
    ONE kind of slot. kind="expr": hooks the language's expression ladder
    (see `expr()` below)."""
    field: str
    kind: str
    doc: str = ""


@dataclass
class Group:
    """One sub-term functor(...), built by walking nested `parts`. Use for
    one comma_list item that is more than a single Cap — a schema field
    `name:type`, a join side `rel BY key`, a split branch `rel IF cond`."""
    functor: str
    parts: list
    doc: str = ""


@dataclass
class CommaList:
    """`field`: SEP-separated repetition of one `parts`-shaped item (a
    single Cap, RuleRef, or a Group), folded to a Prolog list term. min=1
    requires at least one item (Pig never writes an empty list in this
    corpus); min=0 allows zero. `sep` is the separator between items —
    defaults to a bare comma (SYM(",")), Pig's and most of Hive's shape;
    pass a different `sep` (e.g. [kw("UNION"), kw("ALL")], or [] for
    bare juxtaposition — Hive's CASE's WHEN..THEN clauses repeat with no
    separator token at all) via `sep_list()` below."""
    field: str
    parts: list
    min: int = 1
    doc: str = ""
    sep: list = field(default_factory=lambda: [SYM(",")])


@dataclass
class Choice:
    """Exactly one optional keyword from `options` (source spelling -> value
    atom, e.g. {"ASC": "asc", "DESC": "desc"}); contributes the bare atom
    `default` (zero tokens) when none of `options` is present. For
    'ORDER ... BY key [ASC|DESC]'."""
    field: str
    options: dict
    default: Optional[str] = None
    doc: str = ""


@dataclass
class Opt:
    """`parts` present as a whole unit, or absent as a whole unit. Present
    contributes some(Value) (Value from the one Cap/Group inside `parts`
    that carries a value); absent contributes the atom none. At most one
    Opt per parts sequence — gen_prolog.py expands it into two DCG clauses
    for the containing Statement/Group, and does not handle more than one
    (no statement in this corpus needs it)."""
    parts: list
    doc: str = ""


@dataclass
class Statement:
    """One whole statement. `parts` is the full shape, source order,
    EXCLUDING the trailing statement-end symbol — gen_prolog.py appends
    that itself from the spec's own `statement_end`, so no statement()
    call needs to repeat it. assign=True means the source reads
    "REF = <parts>" and the built term is assign(rel(Ref), name(...))."""
    name: str
    parts: list
    assign: bool = False
    doc: str = ""


def kw(text):
    return KW(text)


def sym(text):
    return SYM(text)


def ref(field, doc=""):
    """A WORD token that names a relation: rel(Atom)."""
    return Cap(field, "ref", doc)


def ident(field, doc=""):
    """A WORD token used as a plain name, not a relation: bare Atom."""
    return Cap(field, "ident", doc)


def typename(field, doc=""):
    """A WORD OR KEYWORD token used as a plain name: bare Atom. See
    Cap's docstring for why this is a separate, narrower kind than
    `ident`."""
    return Cap(field, "typename", doc)


def expr(field, doc=""):
    """Hooks this slot into the language's expression ladder (leaf/level/ladder above)."""
    return Cap(field, "expr", doc)


def raw(field, token_kind, doc=""):
    """exp_42 (2026-09-05): one token of kind `token_kind` (a tokeniser leaf
    that swallows a whole raw block, e.g. SAS `datalines; ... `) captured as
    its trimmed BODY text (everything after the first `;`, whitespace
    trimmed at both ends): the term argument is that body as an atom.
    Print puts the head back: `<token_kind>;` NEWLINE body NEWLINE."""
    return Cap(field, "raw:" + token_kind, doc)


def group(functor, *parts, doc=""):
    return Group(functor, list(parts), doc)


def comma_list(field, *parts, min=1, doc=""):
    return CommaList(field, list(parts), min, doc)


def sep_list(field, sep, *parts, min=1, doc=""):
    """Same as comma_list, but the separator between items is `sep` (a
    list of KW/SYM pieces) instead of a bare comma — Hive's `UNION ALL`-
    chained SELECTs (sep=[kw("UNION"), kw("ALL")]) and its CASE
    WHEN..THEN clauses, which just repeat with no separator (sep=[])."""
    return CommaList(field, list(parts), min, doc, list(sep))


@dataclass
class RuleAlt:
    """One shape alternative for a named Rule (see `rules()`/`rule_ref()`
    below): `functor` names the term this alt builds, `parts` is its
    shape — same vocabulary a Statement's `parts` uses. A Rule with more
    than one RuleAlt is an EITHER/OR (e.g. Hive's `from_source`: a bare
    table, or a parenthesised subquery), tried in order — same
    Prolog-backtracking discipline `forms` already uses for expr atoms."""
    functor: str
    parts: list
    doc: str = ""


def rule_alt(functor, *parts, doc=""):
    return RuleAlt(functor, list(parts), doc)


@dataclass
class RuleRef:
    """One piece: parse/print by calling a named Rule — see `rules()` on
    the language's LANG dict (a plain {name: [RuleAlt, ...]} dict, read
    by pipeline/gen_prolog.py's gen_rules()). Referenced by NAME (a
    string), not by Python object identity, which is what lets a Rule
    call itself or another Rule that calls it back — genuine recursion,
    e.g. Hive's `select_core` embeds `from_source`, and `from_source`'s
    subquery alt embeds `select_core` right back."""
    field: str
    name: str
    doc: str = ""


def rule_ref(field, name, doc=""):
    return RuleRef(field, name, doc)


@dataclass
class PartsForm:
    """An expr-atom `form` (alongside pydsl_lib.form's fixed shape-string
    vocabulary above) whose shape is a literal `parts` sequence — for an
    atom that doesn't fit any of that small fixed vocabulary, e.g. Hive's
    `CASE WHEN c THEN e ... [ELSE e] END` or `CAST ( e AS type )`. Built
    and printed exactly like a Group's parts, but as `expr_own/3`
    (precedence 100, atomic — same as every other form) instead of a
    named auxiliary predicate."""
    name: str
    parts: list
    doc: str = ""


def parts_form(name, *parts, doc=""):
    return PartsForm(name, list(parts), doc)


@dataclass
class RuleForm:
    """An expr-atom form shaped `( <rule> )` — a parenthesised named Rule
    used as a value, e.g. Hive's scalar subquery `t.total_amount > (
    SELECT AVG(...) FROM ... )`. Distinct from `form(name, "( E )")`
    (a parenthesised plain EXPRESSION) because the parens here wrap a
    whole Rule (SELECT, with its own FROM/WHERE/...), not `expr`."""
    name: str
    rule_name: str
    doc: str = ""


def rule_form(name, rule_name, doc=""):
    return RuleForm(name, rule_name, doc)


def choice(field, options, default=None, doc=""):
    return Choice(field, options, default, doc)


def opt(*parts, doc=""):
    return Opt(list(parts), doc)


def statement(name, *parts, assign=False, doc=""):
    return Statement(name, list(parts), assign, doc)
