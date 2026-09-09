"""pipeline.specs.hive — HiveQL tokeniser spec.

Why: HiveQL DDL/DML (CREATE TABLE ... AS SELECT, WHERE/CASE/JOIN/GROUP BY,
INSERT ... SELECT ... UNION ALL) has to become a flat, lossless token stream
before folding/parsing can touch it. This module carries no logic of its
own — it is data read by pipeline/tokeniser.py's tokenise(spec, text)
(see that module for the exact contract: leaf-order-wins matching,
single-char symbol fallback, EOS markers, the losslessness assertion).

Inputs -> outputs: read against the six corpus files in
corpus/hive/small/*.hql; exports one dict, LANG, with keys name/keywords/
leaves/statement_end as pipeline.tokeniser expects.

Leaf order (first match at the current position wins):
  1. line comment       -- ... to end of line
  2. block comment      /* ... */, may span newlines, non-greedy
  3. whitespace          spaces/tabs/newlines, run-length
  4. single-quoted string  '...' — a quote inside is escaped either by
     doubling it ('') or with a backslash (\'); \\ escapes a backslash
  5. double-quoted string  "..." — same two escapes ("" and \")
  6. backtick identifier  `...` — kind is WORD (Hive's quoted-identifier
     escape hatch for names that collide with keywords or hold spaces)
  7. number               123 or 123.456 (optional decimal part)
  8. word                 [A-Za-z_][A-Za-z0-9_]* — keyword-checked by the
     engine against `keywords` below (casefolded)
  9. multi-char symbol    <> != <= >= == ||
  Anything left over (single chars like ( ) , ; . * = < > + - / etc.) is
  the engine's 1-char symbol fallback — not listed here, per the tokeniser
  contract (no leaf ever needs to enumerate the single-char case).

WHY BOTH COMMENT LEAVES COME FIRST. Comments must be consumed whole,
before the string leaves ever get a look at their contents. Without the
block-comment leaf, `/* don't */ SELECT 'a'` breaks badly: `/` and `*`
fall through to the symbol fallback, then the apostrophe in "don't"
opens a string that runs across `*/ SELECT ` to the next quote, so real
SQL is buried inside a string token. Worse, `/* -- note */ SELECT 1;`
lets the inner `--` match the line-comment leaf, which then swallows the
closing `*/` AND the whole statement, so the `;` never emits its EOS.
Both cases stay lossless (the text still joins back byte for byte), which
is exactly why the corpus gate could not catch them — losslessness is
necessary but not sufficient. Order between the two comment leaves does
not matter (`--` and `/*` cannot both match at one position); order
against the string leaves is what does.

WHY THE STRING LEAVES ACCEPT BACKSLASH ESCAPES. Hive supports BOTH ways of
putting a quote inside a literal: doubling it ('') and escaping it (\').
An earlier version of this file handled only the doubling, and the missing
backslash case was a masking bug of the same family as the one above.
`SELECT 'don\'t' AS a, 'ok' AS b FROM t;` tokenised as: string `'don\'`,
word `t`, then string `' AS a, '` — the real SQL `AS a,` ended up buried
INSIDE a string token, and every quote after it was paired off by one.
It stayed perfectly lossless the whole time, so neither the corpus gate
nor the lossless law could see it. The alternatives are disjoint by
construction (a backslash can only be consumed by `\\.`, never by
`[^'\\]`), so there is no ambiguity and no backtracking blow-up on an
unterminated literal.
"""
from pipeline.pydsl.pydsl_lib import (
    leaf, level, ladder, one_of, prefix, list_rhs, form,
    kw, sym, ref, ident, typename, expr, group, comma_list, sep_list,
    choice, opt, statement, rule_alt, rule_ref, parts_form, rule_form,
)

LEAVES = [
    leaf("line_comment", r"--[^\n]*", "comment"),
    leaf("block_comment", r"(?s)/\*.*?\*/", "comment"),
    leaf("whitespace", r"[ \t\r\n]+", "whitespace"),
    leaf("string_single", r"'(?:\\.|''|[^'\\])*'", "string"),
    leaf("string_double", r'"(?:\\.|""|[^"\\])*"', "string"),
    leaf("backtick_ident", r"`[^`]*`", "word"),
    leaf("number", r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", "number"),
    leaf("word", r"[A-Za-z_][A-Za-z0-9_]*", "word"),
    leaf("multi_symbol", r"<>|!=|<=|>=|==|\|\|", "symbol"),
]

# HiveQL keywords used by the corpus (corpus/hive/small/*.hql) plus the
# common rest of the DDL/DML surface. Matched case-insensitively against
# WORD tokens by the engine — kept lowercase here by convention.
KEYWORDS = [
    # DDL: CREATE ... TABLE / ROW FORMAT / LOCATION / TBLPROPERTIES
    "create", "external", "table", "row", "format", "delimited",
    "fields", "terminated", "by", "location", "tblproperties",
    "if", "not", "exists",
    # DML: SELECT / FROM / WHERE / GROUP / HAVING / ORDER / LIMIT
    "select", "from", "where", "as",
    "group", "having", "order", "limit", "desc", "asc",
    # joins
    "join", "on", "left", "right", "inner", "outer", "full",
    # CASE / conditional expressions
    "case", "when", "then", "else", "end", "cast", "coalesce",
    # INSERT / set operations
    "insert", "into", "overwrite", "union", "all", "distinct",
    # boolean / predicate operators
    "and", "or", "is", "null", "like", "in", "between",
    # column data types (appear in CREATE TABLE column lists in the corpus)
    "int", "bigint", "smallint", "tinyint", "double", "float",
    "decimal", "string", "boolean", "date", "timestamp",
    "varchar", "char", "array", "map", "struct",
]

# ---------------------------------------------------------------------------
# Phase C — statement grammar (owner, 2026-08-24). Covers EXACTLY what
# corpus/hive/small/*.hql uses: CREATE EXTERNAL TABLE, CREATE TABLE .. AS
# SELECT, a bare CREATE TABLE (cols) with no AS SELECT, INSERT INTO ..
# SELECT, and the SELECT shape itself (proj list, FROM with an optional
# single JOIN, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT, UNION ALL, and a
# scalar/table subquery in WHERE/FROM). Read gen_prolog.py's module
# docstring for what each piece compiles to; this file only says WHAT the
# shape is, never HOW it becomes a DCG.
#
# Term vocabulary (same spirit as pig.py's — a table IS a relation, so
# CREATE/INSERT's table name reads through `ref()` -> rel(Atom), same as
# a Pig alias):
#   rel(Atom)              a table name, defined or referenced
#   col(Atom)               an unqualified column reference
#   col(Rel,Field)          a qualified column reference — o.order_id,
#                            c.name — Hive has no "::" alternative, so
#                            unlike pig.py "." IS the canonical print here
#   lit(V)                  a literal — a real Prolog number, or a
#                            dequoted atom (single- or double-quoted
#                            source string, both fold the same way)
#   call(Name,Args)         a function call — COALESCE(x,0.0), COUNT(*),
#                            SUM(x), AVG(x) all fold through this one
#                            shape, same as pig.py's UDF calls
#   star                    the bare `*` in COUNT(*)
#   cast(Expr,Type)         CAST(expr AS type)
#   case_expr(Whens,Else)   CASE WHEN c THEN e ... [ELSE e] END — Whens a
#                            list of when(Cond,Then), Else none|some(E)
#   field(Name,Type)        one `name type` pair inside a column list
#   prop(Key,Val)           one TBLPROPERTIES ('key'='val') pair
#   proj(Expr,AliasOpt)     one SELECT-list projection, AliasOpt is
#                            none | some(Atom) (from an optional AS)
#   table(rel(N),AliasOpt)  a FROM/JOIN source that is a bare table
#   subquery(Core,Alias)    a FROM/JOIN source that is a parenthesised
#                            SELECT (always aliased in this corpus)
#   join(Source,OnExpr)     the (at most one, per this corpus) JOIN
#   orderby(Key,Dir)        one ORDER BY key [ASC|DESC]
#   select_core(Cols,From,JoinOpt,WhereOpt,GroupByOpt,HavingOpt)
#                            one SELECT ... FROM ... [JOIN ... ON ...]
#                            [WHERE ...] [GROUP BY ...] [HAVING ...] —
#                            NO OrderBy/Limit of its own: those bind to
#                            the whole UNION ALL chain, not to one branch
#                            (see select_stmt below) — same as real SQL.
#   select_stmt(Cores,OrderByOpt,LimitOpt)
#                            Cores a NON-EMPTY list of select_core (length
#                            1 for a plain SELECT, 2 for one UNION ALL —
#                            this corpus never chains more), then the
#                            union-wide [ORDER BY ...] [LIMIT ...]
#   create_external(rel(N),Cols,Delim,Location,Prop)
#   create_table_as(rel(N),SelectStmt)
#   create_table_cols(rel(N),Cols)
#   insert_select(rel(N),SelectStmt)

# ---- expression ladder: or > and > not > comparisons > add/sub > mul/div
# > atoms (tightest first, per pydsl_lib.ladder's convention — same order
# pig.py uses, minus pig's unary-minus level: no corpus expression here
# needs a leading `-`).
EXPR_LADDER = ladder(
    level("mul", one_of("*", "/", functor={"*": "mul", "/": "div"})),
    level("add", one_of("+", "-", functor={"+": "add", "-": "sub"})),
    level("cmp",
          one_of("=", "!=", "<>", "<=", ">=", "<", ">", "like",
                 functor={"=": "eq", "!=": "ne", "<>": "ne", "<=": "le",
                          ">=": "ge", "<": "lt", ">": "gt", "like": "like"})
          + list_rhs("in", functor="in"),
          assoc="none",
          doc="comparisons do not chain: a = b = c is not an expression; "
              "`in` is list_rhs — its right side is `( e, e, ... )`, not a "
              "bare atom, e.g. status IN ('COMPLETED', 'PENDING')"),
    level("not", prefix("not", functor="not")),
    level("and", one_of("and", functor="and")),
    level("or", one_of("or", functor="or")),
)

# ---- forms: fixed shape-string forms (shared vocabulary with pig.py) plus
# two Hive-only atoms (CASE, CAST) that don't fit that fixed vocabulary,
# plus one RuleForm — a parenthesised SELECT used as a value (the scalar
# subquery in h06's WHERE clause).
CASE_WHEN = group("when", kw("WHEN"), expr("cond"), kw("THEN"), expr("then"),
                   doc="one WHEN cond THEN e branch inside a CASE")
CASE_FORM = parts_form(
    "case_expr", kw("CASE"),
    sep_list("whens", [], CASE_WHEN, min=1),
    opt(kw("ELSE"), expr("else")),
    kw("END"),
    doc="CASE WHEN cond THEN e [WHEN cond THEN e ...] [ELSE e] END")
CAST_FORM = parts_form("cast", kw("CAST"), sym("("), expr("e"), kw("AS"), typename("type"), sym(")"),
                        doc="CAST ( expr AS type )")
STAR_FORM = parts_form("star", sym("*"), doc="the bare `*` argument in COUNT(*)")

EXPR_FORMS = [
    CASE_FORM,
    CAST_FORM,
    STAR_FORM,
    form("call", "ID ( ARGS )", doc="function/aggregate call: COALESCE(x,0.0), COUNT(*), SUM(x), AVG(x)"),
    form("col", "ID . ID (canonical)", doc="dot-qualified column: o.order_id, c.name, t.total_amount"),
    rule_form("subquery_expr", "select_core",
              doc="a parenthesised SELECT used as a value — h06's scalar "
                  "subquery: t.total_amount > ( SELECT AVG(...) FROM ... )"),
]

# ---- leaves: atoms at the bottom of the ladder. Leaf name == token kind.
EXPR_LEAVES = [
    leaf("number", "", "lit(V)", doc="a NUMBER token folds to a real Prolog number"),
    leaf("string", "", "lit(V)", doc="a STRING token, quotes stripped and backslash-escapes "
         "decoded (2026-08-26); double_delim=True because hive.py's own string_single/"
         "string_double tokeniser leaves both admit a doubled delimiter ('' / \"\") as an "
         "in-string escape on top of \\X, per this file's own docstring lines 18-20",
         dequote=True, double_delim=True),
    leaf("word", "", "col(V)", doc="a bare WORD token used as an unqualified column"),
]

# ---- shared sub-shapes, referenced from more than one statement/rule ----
SCHEMA_FIELD = group("field", ident("name"), typename("type"),
                      doc="one `name type` pair inside a CREATE TABLE column list — "
                          "`type` is typename(), not ident(), because INT/DOUBLE/"
                          "STRING/... are themselves entries in this file's own "
                          "`keywords`, so the tokeniser hands them back tagged "
                          "keyword, not word (see pydsl_lib.Cap's docstring)")
PROJ = group("proj", expr("e"), opt(kw("AS"), ident("as")),
             doc="one SELECT-list projection, optionally renamed")

# ---- named rules: from_source and select_core are MUTUALLY RECURSIVE —
# from_source's "subquery" alt embeds select_core, and select_core's FROM
# (and optional JOIN) embed from_source right back. h06 exercises this to
# depth 2 (a FROM subquery inside a FROM subquery, via the avg_sub scalar
# subquery). Resolved purely by NAME (rule_ref), never by Python object
# identity — see pydsl_lib.RuleRef's docstring.
RULES = {
    "from_source": [
        rule_alt("table", ref("rel"), opt(ident("as")),
                 doc="a bare table, optionally aliased: `orders`, `orders o`"),
        rule_alt("subquery", sym("("), rule_ref("core", "select_core"), sym(")"), ident("as"),
                 doc="a parenthesised SELECT, always aliased in this corpus: "
                     "`( SELECT ... ) t`"),
    ],
    "select_core": [
        rule_alt(
            "select_core",
            kw("SELECT"), comma_list("cols", PROJ, min=1),
            kw("FROM"), rule_ref("from", "from_source"),
            opt(kw("JOIN"), group("join", rule_ref("src", "from_source"), kw("ON"), expr("on"))),
            opt(kw("WHERE"), expr("where")),
            opt(kw("GROUP"), kw("BY"), comma_list("groupby", expr("k"), min=1)),
            opt(kw("HAVING"), expr("having")),
            doc="SELECT cols FROM from_source [JOIN from_source ON e] [WHERE e] "
                "[GROUP BY e,...] [HAVING e] — no ORDER BY/LIMIT of its own",
        ),
    ],
    "select_stmt": [
        rule_alt(
            "select_stmt",
            sep_list("cores", [kw("UNION"), kw("ALL")], rule_ref("core", "select_core"), min=1),
            opt(kw("ORDER"), kw("BY"),
                group("orderby", expr("key"), choice("dir", {"ASC": "asc", "DESC": "desc"}, default="asc"))),
            opt(kw("LIMIT"), expr("n")),
            doc="select_core (UNION ALL select_core)* [ORDER BY key [ASC|DESC]] [LIMIT n] — "
                "ORDER BY/LIMIT bind to the whole chain, same as real SQL",
        ),
    ],
}

STATEMENTS = [
    statement(
        "create_external",
        kw("CREATE"), kw("EXTERNAL"), kw("TABLE"), ref("name"),
        sym("("), comma_list("cols", SCHEMA_FIELD, min=1), sym(")"),
        kw("ROW"), kw("FORMAT"), kw("DELIMITED"), kw("FIELDS"), kw("TERMINATED"), kw("BY"), expr("delim"),
        kw("LOCATION"), expr("location"),
        kw("TBLPROPERTIES"), sym("("), group("prop", expr("key"), sym("="), expr("val")), sym(")"),
        doc="CREATE EXTERNAL TABLE name (cols) ROW FORMAT DELIMITED FIELDS "
            "TERMINATED BY delim LOCATION loc TBLPROPERTIES (key=val)",
    ),
    statement(
        "create_table_as",
        kw("CREATE"), kw("TABLE"), ref("name"), kw("AS"), rule_ref("select", "select_stmt"),
        doc="CREATE TABLE name AS select_stmt",
    ),
    statement(
        "create_table_cols",
        kw("CREATE"), kw("TABLE"), ref("name"),
        sym("("), comma_list("cols", SCHEMA_FIELD, min=1), sym(")"),
        doc="CREATE TABLE name (cols) — no AS SELECT (h05's target-shape table)",
    ),
    statement(
        "insert_select",
        kw("INSERT"), kw("INTO"), ref("name"), rule_ref("select", "select_stmt"),
        doc="INSERT INTO name select_stmt",
    ),
]

LANG = {
    "name": "hive",
    "ext": ".hql",
    "keywords": KEYWORDS,
    "leaves": LEAVES,
    "statement_end": [";"],
    # Phase C (pipeline/gen_prolog.py reads these; pipeline/tokeniser.py never does):
    "ladder": EXPR_LADDER,
    "forms": EXPR_FORMS,
    "expr_leaves": EXPR_LEAVES,
    "statements": STATEMENTS,
    "rules": RULES,
}
