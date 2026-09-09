"""pig.py — Pig Latin tokeniser spec for the exp_014 vertical slice.

Why this file exists: the tokeniser engine (pipeline/tokeniser.py) is
language-blind. It only knows how to try a list of `leaf` regexes in
order and fall back to a 1-char symbol when none match. This module is
the language-specific half of that contract: it says what a Pig Latin
source byte stream is made of, in the order those things must be tried.

ORDER MATTERS. re.match is tried leaf-by-leaf at the current offset; the
first leaf whose pattern matches wins. Comments must come before
whitespace (both start with characters whitespace could also start
with-ish, and `--`/`/*` must not be mistaken for symbols). Strings must
come before word/number so a quoted digit or keyword-looking text inside
'...' is never re-lexed. Numbers before word so `2` isn't swallowed by
nothing else. Multi-char symbols (`::`, `..`, `==`, `!=`, `<=`, `>=`)
must come before the engine's 1-char symbol fallback, or `a::b` would
tokenise as `:` `:` instead of `::`. Everything left over — `=`, `,`,
`(`, `)`, `:`, `;`, `.`, `*`, `+`, `-`, `<`, `>`, `$`, `@`, `#`, `%` —
is legal by construction as a 1-char symbol; the engine handles that,
this spec doesn't need a leaf for any of them.

Keyword set: the classic Pig Latin relational/control words actually
used across corpus/pig/small/*.pig (load, using, as, filter, by,
foreach, generate, group, join, order, limit, distinct, union, split,
into, if, store, desc), plus the rest of the commonly-used set that
belongs alongside them even though the 6-file corpus doesn't happen to
use it (and, or, not, is, null, asc, all, any, matches, flatten,
parallel). Function/UDF names like SUM, COUNT, AVG, PigStorage are
deliberately NOT keywords — they're ordinary WORD tokens, same as a
relation alias, because Pig Latin does not reserve them.
"""
from pipeline.pydsl.pydsl_lib import (
    leaf, level, ladder, one_of, prefix, form,
    kw, sym, ref, ident, expr, group, comma_list, choice, opt, statement,
)

# ---------------------------------------------------------------------------
# Phase C — statement grammar (owner, 2026-08-24). Originally covered
# EXACTLY what corpus/pig/small/*.pig used: LOAD/FILTER/FOREACH-GENERATE/
# GROUP/JOIN/ORDER/LIMIT/DISTINCT/UNION/SPLIT/STORE. Extended 2026-08-26
# with CROSS/COGROUP/REGISTER, driven by real apache/pig corpus evidence
# (see code_graph/gold/pig/coverage.md's "Grammar extension" section for
# the exact citations and what's still not covered). Read gen_prolog.py's
# module docstring for what each piece compiles to; this file only says
# WHAT the shape is, never HOW it becomes a DCG.
#
# Term vocabulary (same spirit as the phase-C contract's own example,
# assign(rel(b), filter(rel(a), gt(col(v), lit(15))))):
#   rel(Atom)        a relation alias, defined or referenced
#   col(Atom)        an unqualified column reference
#   col(Rel,Field)   a qualified column reference — raw_txn.amount (inside a
#                    grouped bag) and raw_txn::txn_id (after JOIN) both fold
#                    to this SAME functor; the printer always spells it `::`
#   lit(V)           a literal — V is a real Prolog number, or a dequoted atom
#   call(Name,Args)  a function call — PigStorage(','), SUM(x), COUNT(x)
#   group            the bare pseudo-column FOREACH binds to a GROUP BY key
#   pos(N)           a positional field, $0, $1, ... (not in this corpus)

# ---- expression ladder: or > and > not > comparisons > add/sub > mul/div
# > unary minus > atoms (tightest first, per pydsl_lib.ladder's convention)
EXPR_LADDER = ladder(
    level("unary", prefix("-", functor="neg"),
          doc="unary minus binds tighter than * and /"),
    level("mul", one_of("*", "/", functor={"*": "mul", "/": "div"})),
    level("add", one_of("+", "-", functor={"+": "add", "-": "sub"})),
    level("cmp", one_of("==", "!=", ">", ">=", "<", "<=", "matches",
                        functor={"==": "eq", "!=": "ne", ">": "gt", ">=": "ge",
                                 "<": "lt", "<=": "le", "matches": "matches"}),
          assoc="none", doc="comparisons do not chain: a > b > c is not an expression"),
    level("not", prefix("not", functor="not")),
    level("and", one_of("and", functor="and")),
    level("or", one_of("or", functor="or")),
)

# ---- forms: the finite shape-string vocabulary gen_prolog.py interprets
EXPR_FORMS = [
    form("paren", "( E )", doc="a source paren, kept in the term: amount - (amount * 0.02)"),
    form("call", "ID ( ARGS )", doc="function call: PigStorage(','), SUM(x), COUNT(x), AVG(x)"),
    form("col", "ID . ID", doc="dot-qualified field inside a grouped bag: raw_txn.amount"),
    form("col", "ID :: ID", doc="::-qualified field after JOIN: raw_txn::txn_id"),
    form("group_ref", "KW group", doc="the bare keyword `group`, folds to the atom `group`"),
    form("pos", "$ NUM", doc="positional field $0, $1, ... -- e.g. `cogroup A by $0 inner` (apache/pig TestParser.pig)"),
    form("param", "$ ID", doc="a $NAME parameter-substitution reference -- REGISTER $PIGMIX_JAR, "
                              "`... parallel $PARALLEL` (apache/pig pigmix L1.pig/L5.pig)"),
]

# ---- leaves: atoms at the bottom of the ladder. Leaf name == token kind.
EXPR_LEAVES = [
    leaf("number", "", "lit(V)", doc="a NUMBER token folds to a real Prolog number"),
    leaf("string", "", "lit(V)", doc="a STRING token, quotes stripped", dequote=True),
    leaf("word", "", "col(V)", doc="a bare WORD token used as an unqualified column"),
    leaf("path", "", "resource(V)", doc="an unquoted resource path token (see LANG['leaves'] "
                                        "below) -- REGISTER ./tutorial.jar (apache/pig tutorial)"),
]

# ---- statements: EXACTLY the shapes corpus/pig/small/*.pig uses, PLUS
# cross/cogroup/register (2026-08-26 extension — see gold/pig/coverage.md's
# "Update" section for the real apache/pig files that drove each shape).
SCHEMA_FIELD = group("field", ident("name"), sym(":"), ident("type"),
                      doc="one `name:type` pair inside a LOAD ... AS (...) schema")
PROJ = group("proj", expr("e"), opt(kw("AS"), ident("as")),
             doc="one FOREACH ... GENERATE projection, optionally renamed")
JOIN_SIDE = group("side", ref("rel"), kw("BY"), expr("key"),
                   doc="one side of a JOIN: `rel BY key`")
SPLIT_BRANCH = group("branch", ref("into"), kw("IF"), expr("cond"),
                      doc="one SPLIT ... INTO branch: `alias IF cond`")
COGROUP_SIDE = group("side", ref("rel"), kw("BY"), expr("key"),
                      choice("mode", {"INNER": "inner", "OUTER": "outer"}, default="outer"),
                      doc="one side of a COGROUP: `rel BY key [INNER|OUTER]` -- unspecified "
                          "reads as (and always re-prints as) OUTER, same convention ORDER's "
                          "ASC/DESC choice already uses for an omittable-but-always-printed "
                          "modifier; apache/pig TestParser.pig's `D = cogroup A by $0 inner, "
                          "B by $0 outer;` exercises both spellings explicitly")

STATEMENTS = [
    statement("load", kw("LOAD"), expr("path"), kw("USING"), expr("using"),
              kw("AS"), sym("("), comma_list("schema", SCHEMA_FIELD, min=1), sym(")"),
              assign=True, doc="alias = LOAD 'path' USING PigStorage(',') AS (f:t, ...)"),
    statement("filter", kw("FILTER"), ref("rel"), kw("BY"), expr("cond"),
              assign=True, doc="alias = FILTER rel BY cond"),
    statement("foreach", kw("FOREACH"), ref("rel"), kw("GENERATE"),
              comma_list("projs", PROJ, min=1),
              assign=True, doc="alias = FOREACH rel GENERATE proj, proj AS name, ..."),
    statement("group", kw("GROUP"), ref("rel"), kw("BY"), expr("key"),
              assign=True, doc="alias = GROUP rel BY key"),
    statement("join", kw("JOIN"), comma_list("sides", JOIN_SIDE, min=2),
              assign=True, doc="alias = JOIN rel1 BY k1, rel2 BY k2"),
    statement("order", kw("ORDER"), ref("rel"), kw("BY"), expr("key"),
              choice("dir", {"ASC": "asc", "DESC": "desc"}, default="asc"),
              assign=True, doc="alias = ORDER rel BY key [ASC|DESC]"),
    statement("limit", kw("LIMIT"), ref("rel"), expr("n"),
              assign=True, doc="alias = LIMIT rel n"),
    statement("distinct", kw("DISTINCT"), ref("rel"),
              assign=True, doc="alias = DISTINCT rel"),
    statement("union", kw("UNION"), comma_list("rels", ref("rel"), min=2),
              assign=True, doc="alias = UNION rel1, rel2, ..."),
    statement("split", kw("SPLIT"), ref("rel"), kw("INTO"),
              comma_list("branches", SPLIT_BRANCH, min=1),
              doc="SPLIT rel INTO alias IF cond, alias IF cond, ... (no assignment)"),
    statement("store", kw("STORE"), ref("rel"), kw("INTO"), expr("path"), kw("USING"), expr("using"),
              doc="STORE rel INTO 'path' USING PigStorage(',') (no assignment)"),
    statement("cross", kw("CROSS"), comma_list("rels", ref("rel"), min=2),
              assign=True, doc="alias = CROSS rel1, rel2, ... -- same shape as UNION; "
                                "apache/pig tutorial script2-hadoop.pig: `F = Cross A, B;`"),
    statement("cogroup", kw("COGROUP"), comma_list("sides", COGROUP_SIDE, min=2),
              opt(kw("PARALLEL"), expr("parallel")),
              assign=True, doc="alias = COGROUP rel1 BY k1 [INNER|OUTER], rel2 BY k2 [INNER|OUTER], "
                                "... [PARALLEL n] -- apache/pig pigmix L5.pig and TestParser.pig"),
    statement("register", kw("REGISTER"), expr("path"),
              doc="REGISTER path -- path is a quoted string, a $VAR, or an unquoted resource "
                  "path (./tutorial.jar); no assignment. apache/pig tutorial script1-local.pig "
                  "(REGISTER ./tutorial.jar;) and pigmix L1.pig (register $PIGMIX_JAR) -- the "
                  "pigmix spelling has no trailing semicolon in the real file, which this "
                  "project's tokeniser/statement-splitter treats as still-open (documented in "
                  "gold/pig/coverage.md, not fixed here: it is a shared, cross-language "
                  "splitter behavior, not a pig.py grammar gap)"),
]

LANG = {
    "name": "pig",
    "ext": ".pig",
    "keywords": [
        "load", "using", "as", "filter", "by", "foreach", "generate",
        "group", "join", "order", "limit", "distinct", "union", "split",
        "into", "if", "store", "and", "or", "not", "is", "null",
        "asc", "desc", "all", "any", "matches", "flatten", "parallel",
        # 2026-08-26 extension: cross/cogroup/register
        "cross", "cogroup", "inner", "outer", "register",
    ],
    "leaves": [
        # comments: `-- to end of line` and `/* ... */` (DOTALL so a block
        # comment can span newlines); both must be tried before whitespace
        # so `--` and `/*` are never mistaken for symbol runs.
        leaf("comment_line", r"--[^\n]*", "comment"),
        leaf("comment_block", r"(?s)/\*.*?\*/", "comment"),
        # whitespace: runs of spaces/tabs/CR/LF, one token per run.
        leaf("whitespace", r"[ \t\r\n]+", "whitespace"),
        # strings: single-quoted, backslash-escapes anything incl. `\'`.
        leaf("string", r"'(?:\\.|[^'\\])*'", "string"),
        # resource paths: an unquoted REGISTER argument like `./tutorial.jar`
        # or `../lib/foo-1.0.jar` — one token, kind "path" (2026-08-26
        # extension). Must come before "number" (irrelevant here — this
        # never starts with a digit) and does not compete with "word" (a
        # word can't start with `.`) or "op2"'s `..` range spelling (that
        # pattern alone never has a following `/`, so `\.{1,2}/` is a
        # strictly narrower, non-overlapping match tried first anyway).
        leaf("path", r"\.{1,2}/[\w./\-]*", "path"),
        # numbers: ints and decimals — `100`, `0.02`, `100.0`.
        leaf("number", r"\d+(?:\.\d+)?", "number"),
        # words: identifiers and keywords (keyword-ness is decided by the
        # engine casefolding against LANG["keywords"], not here).
        leaf("word", r"[A-Za-z_][A-Za-z0-9_]*", "word"),
        # multi-char symbols BEFORE the engine's 1-char fallback:
        #   :: field-disambiguation (raw_txn::txn_id), .. range,
        #   ==/!=/<=/>= comparisons. Single `:` `.` `=` `<` `>` are still
        #   legal — they just fall through to the engine's 1-char symbol.
        leaf("op2", r"::|\.\.|==|!=|<=|>=", "symbol"),
    ],
    "statement_end": [";"],
    # Phase C (pipeline/gen_prolog.py reads these; pipeline/tokeniser.py never does):
    "ladder": EXPR_LADDER,
    "forms": EXPR_FORMS,
    "expr_leaves": EXPR_LEAVES,
    "statements": STATEMENTS,
}
