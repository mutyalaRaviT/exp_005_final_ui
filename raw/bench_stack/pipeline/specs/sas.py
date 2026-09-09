"""pipeline.specs.sas — the SAS pyDSL for exp_42 (2026-09-05).

Why: one Python spec, written once, from which pipeline/gen_prolog.py
generates the Prolog DCG (parse AND print) and pipeline/export_spec.py
exports the JSON the Rust engine (rust_engine/) interprets. Nothing in
this file is code; it is the description of SAS as data — tokens, the
expression ladder, statement shapes, and the block law.

Scope: exactly the constructs corpus/sas/test_vishnu.sas uses, written in
their general shape so a sibling program with more columns, more
statements or more PROC SQL clauses still folds:
    LIBNAME lib 'path';
    DATA lib.ds;  INPUT v $ v v :informat.;  FORMAT v fmt.;  DATALINES; ... ;  RUN;
    DATA lib.ds;  SET lib.ds;  IF cond;  RUN;
    DATA lib.ds;  MERGE lib.ds(IN=a) lib.ds(IN=b);  BY k;  RUN;
    PROC SQL;  CREATE TABLE lib.ds AS SELECT ... FROM ... [WHERE ...] [GROUP BY ...];  ;  RUN|QUIT;

Term vocabulary (what node/4 holds — read this once, the terms then read themselves):
    ds(Lib,Name) | ds(Name)        a dataset reference
    libname(Lib, lit(Path))
    data(ds(..))                   DATA statement (opens a step; the step's OUTPUT)
    input([cvar(N) | nvar(N, none|some(informat(F))) ...])
    format(Var, fmt(F))
    datalines(Body)                the raw rows, one atom, rows separated by newlines
    set(ds(..))
    if_then_set(Var, lit(V), ds(..))   IF _N_ = 1 THEN SET: a one-row lookup attached to every row
    subset_if(Cond)                a subsetting IF
    merge([src(ds(..), none|some(Flag)) ...])
    by([Key ...])
    proc_sql
    create_table_as(ds(..), select_stmt([select_core(Cols, From, JoinOpt, WhereOpt, GroupByOpt, HavingOpt) ...], OrderByOpt, LimitOpt))
        Cols  = [proj(Expr, none|some(Alias)) ...]
        From  = table(ds(..), none|some(Alias)) | subquery(select_core(..), none|some(Alias))
    empty                          a lone `;`
    run | quit
    Expressions: col(N), lit(V), star, call(Name, [Args]), paren(E), subquery_expr(select_core(..)),
        neg/1, mul/div/add/sub/cat, eq/ne/lt/le/gt/ge, in(E, [..]), not/1, and/or.
"""
from pipeline.pydsl.pydsl_lib import (
    leaf, level, ladder, one_of, prefix, list_rhs, form,
    kw, sym, ident, expr, group, comma_list, sep_list, opt, raw,
    statement, rule_alt, rule_ref, parts_form, rule_form,
)

# ---------------------------------------------------------------- tokens
# Order matters: first leaf that matches at the current position wins.
LEAVES = [
    leaf("block_comment", r"(?s)/\*.*?\*/", "comment"),
    leaf("whitespace", r"[ \t\r\n]+", "whitespace"),
    # DATALINES / CARDS: the head, then every following line that holds no
    # ';' — the first ';' ends the block, as SAS itself does. The block is ONE
    # token of kind "datalines" and ends its statement by itself (eos_kinds).
    leaf("datalines", r"(?i)(?:datalines|cards)[ \t]*;(?:\r?\n[^;\n]*)*", "datalines"),
    # SAS strings: the doubled delimiter is the only escape; a backslash is a plain byte.
    leaf("string_single", r"'(?:''|[^'])*'", "string"),
    leaf("string_double", r'"(?:""|[^"])*"', "string"),
    leaf("number", r"\d+(?:\.\d+)?", "number"),
    leaf("word", r"[A-Za-z_][A-Za-z0-9_]*", "word"),
    leaf("multi_symbol", r"<=|>=|\^=|~=|<>|\*\*|\|\|", "symbol"),
]

KEYWORDS = [
    "libname", "data", "set", "print", "title", "if", "merge", "by", "input", "format", "run", "quit",
    "proc", "sql", "create", "table", "as", "select", "from", "where",
    "group", "having", "order", "union", "all", "join", "on", "desc", "asc", "limit",
    "then", "and", "or", "not", "in", "eq", "ne", "lt", "le", "gt", "ge",
]

# ------------------------------------------------------ expression ladder
# Tightest first. Same ladder exp_013 wrote for SAS expressions, in the
# exp_014 vocabulary (left-assoc levels become accumulator loops; `**` is
# one-shot here because the generator has no right-assoc level yet).
EXPR_LADDER = ladder(
    level("pow", one_of("**", functor="pow"), assoc="none",
          doc="exponent; one shot (2 ** 3 ** 2 is not folded — not needed here)"),
    level("unary", prefix("-", functor="neg"), doc="unary minus"),
    level("mul", one_of("*", "/", functor={"*": "mul", "/": "div"})),
    level("add", one_of("+", "-", functor={"+": "add", "-": "sub"})),
    level("cat", one_of("||", functor="cat"), doc="string concatenation"),
    level("cmp",
          one_of("=", "eq", "^=", "~=", "<>", "ne", "<", "lt", "<=", "le", ">", "gt", ">=", "ge",
                 functor={"=": "eq", "eq": "eq", "^=": "ne", "~=": "ne", "<>": "ne", "ne": "ne",
                          "<": "lt", "lt": "lt", "<=": "le", "le": "le",
                          ">": "gt", "gt": "gt", ">=": "ge", "ge": "ge"})
          + list_rhs("in", functor="in"),
          assoc="none",
          doc="comparisons do not chain; `<>` is read as NE (its PROC SQL meaning)"),
    level("not", prefix("not", functor="not")),
    level("and", one_of("and", functor="and")),
    level("or", one_of("or", functor="or")),
)

STAR_FORM = parts_form("star", sym("*"), doc="the bare `*` in SELECT * / COUNT(*)")

EXPR_FORMS = [
    STAR_FORM,
    form("paren", "( E )", doc="a source parenthesis, kept in the term"),
    form("call", "ID ( ARGS )", doc="function or aggregate call: MONTH(date), SUM(x), AVG(x), MAX(x), MIN(x)"),
    form("col", "ID . ID (canonical)", doc="alias-qualified column in PROC SQL: a.col"),
    rule_form("subquery_expr", "select_core", doc="a parenthesised SELECT used as a value: x > (SELECT avg_sales FROM ...)"),
]

EXPR_LEAVES = [
    leaf("number", "", "lit(V)", doc="a NUMBER token folds to a real Prolog number"),
    leaf("string", "", "lit(V)", doc="a STRING token, quotes stripped, '' -> ' (no backslash escapes in SAS)",
         dequote=True, double_delim=True, backslash_escape=False),
    leaf("word", "", "col(V)", doc="a bare WORD used as a column"),
]

# ------------------------------------------------------------ sub-shapes
PROJ = group("proj", expr("e"), opt(kw("AS"), ident("as")), doc="one SELECT-list item, optionally renamed")

RULES = {
    "dsname": [
        rule_alt("ds", ident("lib"), sym("."), ident("name"), doc="lib.dataset"),
        rule_alt("ds", ident("name"), doc="a WORK dataset, no libref"),
    ],
    "input_var": [
        rule_alt("cvar", ident("name"), sym("$"), doc="a character variable: name $"),
        rule_alt("nvar", ident("name"), opt(sym(":"), group("informat", ident("name"), sym("."))),
                 doc="a numeric variable, optionally read with :informat."),
    ],
    "from_source": [
        rule_alt("table", rule_ref("ds", "dsname"), opt(ident("as")), doc="a dataset, optionally aliased"),
        rule_alt("subquery", sym("("), rule_ref("core", "select_core"), sym(")"), opt(ident("as")),
                 doc="a parenthesised SELECT in FROM"),
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
            doc="SELECT cols FROM src [JOIN src ON e] [WHERE e] [GROUP BY e,...] [HAVING e]",
        ),
    ],
    "select_stmt": [
        rule_alt(
            "select_stmt",
            sep_list("cores", [kw("UNION"), kw("ALL")], rule_ref("core", "select_core"), min=1),
            opt(kw("ORDER"), kw("BY"), comma_list("orderby", expr("k"), min=1)),
            opt(kw("LIMIT"), expr("n")),
            doc="select_core (UNION ALL select_core)* [ORDER BY k,...]",
        ),
    ],
}

# ------------------------------------------------------------ statements
STATEMENTS = [
    statement("libname", kw("LIBNAME"), ident("lib"), expr("path"), doc="LIBNAME lib 'path'"),
    statement("data", kw("DATA"), rule_ref("out", "dsname"), doc="DATA lib.ds — opens a step"),
    statement("input", kw("INPUT"), sep_list("vars", [], rule_ref("v", "input_var"), min=1),
              doc="INPUT v $ v v :informat. — list input"),
    statement("format", kw("FORMAT"), ident("var"), group("fmt", ident("name"), sym(".")),
              doc="FORMAT var fmt."),
    statement("datalines", raw("rows", "datalines"), doc="DATALINES; rows ;"),
    statement("set", kw("SET"), rule_ref("in", "dsname"), doc="SET lib.ds"),
    statement("subset_if", kw("IF"), expr("cond"), doc="a subsetting IF: keep the row when cond is true"),
    statement("if_then_set", kw("IF"), ident("var"), sym("="), expr("val"), kw("THEN"), kw("SET"), rule_ref("in", "dsname"),
              doc="IF _N_ = 1 THEN SET lib.ds — read one row once, its variables are retained on every output row"),
    statement("merge", kw("MERGE"),
              sep_list("sources", [], group("src", rule_ref("ds", "dsname"),
                                            opt(sym("("), kw("IN"), sym("="), ident("flag"), sym(")"))), min=1),
              doc="MERGE lib.ds(IN=a) lib.ds(IN=b)"),
    statement("by", kw("BY"), sep_list("keys", [], ident("k"), min=1), doc="BY k1 k2"),
    statement("proc_sql", kw("PROC"), kw("SQL"), doc="PROC SQL — opens a step"),
    statement("create_table_as", kw("CREATE"), kw("TABLE"), rule_ref("out", "dsname"), kw("AS"),
              rule_ref("select", "select_stmt"), doc="CREATE TABLE lib.ds AS select"),
    statement("proc_print", kw("PROC"), kw("PRINT"), kw("DATA"), sym("="), rule_ref("in", "dsname"),
              doc="PROC PRINT DATA=lib.ds — opens a step; the converted program lists every dataset at its end"),
    statement("title", kw("TITLE"), expr("text"), doc="TITLE 'text'"),
    statement("empty", doc="a lone `;`"),
    statement("run", kw("RUN"), doc="RUN — closes a step"),
    statement("quit", kw("QUIT"), doc="QUIT — closes a PROC step"),
]

LANG = {
    "name": "sas",
    "ext": ".sas",
    "keywords": KEYWORDS,
    "leaves": LEAVES,
    "statement_end": [";"],
    "eos_kinds": ["datalines"],
    "ladder": EXPR_LADDER,
    "forms": EXPR_FORMS,
    "expr_leaves": EXPR_LEAVES,
    "statements": STATEMENTS,
    "rules": RULES,
    # block law: one DATA/PROC step = one block; LIBNAME stands alone
    "blocks": {"open": ["data", "proc_sql", "proc_print"], "close": ["run", "quit"], "single": ["libname"]},
}
