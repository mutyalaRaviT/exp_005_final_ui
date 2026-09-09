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
    create_table_as(ds(..), select_stmt([select_core(Cols, From, Joins, WhereOpt, GroupByOpt, HavingOpt) ...], OrderByOpt, LimitOpt))
        Cols  = [proj(Expr, none|some(Alias), none|some(Length)) ...]
        From  = table(ds(..), none|some(Alias)) | subquery(select_core(..), none|some(Alias))
        Joins = [left_join(Src,On) | inner_join(Src,On) ...]   -- task 5c: ZERO OR MORE
            joins, source order, no separator token (each alternative leads with its own
            LEFT/INNER keyword) — was `none | some(...)` (at most one) through task 5b;
            widened because every remaining fold failure in the ankitha corpus was a
            multi-JOIN create_table_as (see the note at select_core's RULES entry below).
    length([clen(Var,N)|nlen(Var,N)])   LENGTH var $ n ... — storage length
    infile(Dlm)                    INFILE DATALINES DSD DLM='delim' TRUNCOVER
    assign(Var, Val)                var = expr — a DATA-step assignment
    output                          OUTPUT — writes the current PDV row
    empty                          a lone `;`
    run | quit
    Expressions: col(N), lit(V), star, missing (a lone `.`), call(Name, [Args]), paren(E),
        case_expr([when(Cond,Then)...], none|some(Else)), subquery_expr(select_core(..)),
        neg/1, mul/div/add/sub/cat, eq/ne/lt/le/gt/ge, in(E, [..]), not/1, and/or,
        distinct/1 (task 5c: COUNT(DISTINCT x) — DISTINCT prefixes an expr, same
        precedence level as unary minus; the ladder does not gate it to aggregate call
        args specifically, same permissiveness as `not` elsewhere in this ladder).
"""
from pipeline.pydsl.pydsl_lib import (
    leaf, level, ladder, one_of, prefix, list_rhs, form,
    kw, sym, ident, expr, group, comma_list, sep_list, opt, raw, choice,
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
    # task 5b (2026-09-09), create_table_as family: LEFT/INNER JOIN (this
    # corpus never writes a bare JOIN), CASE/WHEN/THEN.../END, and LENGTH —
    # PROC SQL's trailing `AS alias LENGTH=n` on one SELECT-list item.
    "left", "inner", "case", "when", "else", "end", "length",
    # task 5b, infile family: INFILE DATALINES DSD DLM='delim' TRUNCOVER —
    # note DATALINES here is a plain keyword read from the WORD side; the
    # dedicated `datalines` tokeniser LEAF (LEAVES above) only fires when
    # the word is immediately followed by `;`, which is not the case inside
    # this option line, so the two never collide.
    "infile", "dsd", "dlm", "truncover", "datalines",
    # task 5b, output family: OUTPUT — writes the current PDV row.
    "output",
    # task 5c: COUNT(DISTINCT x) — grepped the corpus and both regression files for
    # "distinct" used bare (column/table name); none found.
    "distinct",
]

# ------------------------------------------------------ expression ladder
# Tightest first. Same ladder exp_013 wrote for SAS expressions, in the
# exp_014 vocabulary (left-assoc levels become accumulator loops; `**` is
# one-shot here because the generator has no right-assoc level yet).
EXPR_LADDER = ladder(
    level("pow", one_of("**", functor="pow"), assoc="none",
          doc="exponent; one shot (2 ** 3 ** 2 is not folded — not needed here)"),
    # task 5c: DISTINCT shares this level with unary minus — both are bare prefix
    # operators, and SAS only ever writes DISTINCT immediately before an aggregate's
    # argument (COUNT(DISTINCT x)), so binding it this tight never collides with
    # anything the corpus actually writes.
    level("unary", prefix("-", functor="neg") + prefix("distinct", functor="distinct"),
          doc="unary minus; DISTINCT (COUNT(DISTINCT x))"),
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

# task 5b (2026-09-09): CASE WHEN ... END, same shape hive.py already proved
# (pipeline/specs/hive.py's CASE_WHEN/CASE_FORM) — copied here, not re-derived,
# since 13_risk_flags.sas and 17_compliance_check.sas both need it:
#   CASE WHEN c.risk_score >= 0.75 THEN 'HIGH' WHEN ... ELSE 'LOW' END
CASE_WHEN = group("when", kw("WHEN"), expr("cond"), kw("THEN"), expr("then"),
                   doc="one WHEN cond THEN e branch inside a CASE")
CASE_FORM = parts_form(
    "case_expr", kw("CASE"),
    sep_list("whens", [], CASE_WHEN, min=1),
    opt(kw("ELSE"), expr("else")),
    kw("END"),
    doc="CASE WHEN cond THEN e [WHEN cond THEN e ...] [ELSE e] END")

# task 5b: a lone `.` in a SELECT list is SAS's numeric missing value, not a
# stray dot — 25_final_pack.sas's third UNION ALL branch writes `. ,` where a
# real column would go. `.` is otherwise only ever a bare symbol token here
# (lib.dataset, alias.col are both matched from the WORD side, not from `.`),
# so this atom form cannot collide with them.
MISSING_FORM = parts_form("missing", sym("."), doc="a lone `.` — the SAS numeric missing value")

EXPR_FORMS = [
    CASE_FORM,
    MISSING_FORM,
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
# task 5b: `AS alias` and a trailing `LENGTH=n` are independent optional
# tails (SAS PROC SQL lets a projection set an explicit output-column length:
# `'BRANCH' as metric_type length=12`) — two Opts in one parts sequence is
# already how select_core's own WHERE/GROUP BY/HAVING coexist below, so this
# is the same, proven shape, not a new pattern.
PROJ = group("proj", expr("e"), opt(kw("AS"), ident("as")), opt(kw("LENGTH"), sym("="), expr("len")),
             doc="one SELECT-list item, optionally renamed and/or given an explicit output LENGTH")

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
    "length_var": [
        rule_alt("clen", ident("name"), sym("$"), expr("n"), doc="a character variable's length: name $ n"),
        rule_alt("nlen", ident("name"), expr("n"), doc="a numeric variable's length: name n"),
    ],
    "from_source": [
        rule_alt("table", rule_ref("ds", "dsname"), opt(ident("as")), doc="a dataset, optionally aliased"),
        rule_alt("subquery", sym("("), rule_ref("core", "select_core"), sym(")"), opt(ident("as")),
                 doc="a parenthesised SELECT in FROM"),
    ],
    # task 5c: ZERO OR MORE JOINs per select_core — task 5b capped this at one
    # because the Rust lineage engine (rust_rules_converter/src/lineage.rs
    # select_lineage) read select_core's join field positionally as
    # `some(J)`/`none`, reading J's own args()[0]/args()[1] blindly as (src, on)
    # without checking J's functor name. Every remaining fold failure in the
    # ankitha corpus after 5b was exactly this: a create_table_as with 2+ JOINs
    # (04_build_accounts.sas's 2nd block, 11_branch_rollup.sas — phase 2's pass
    # mark 1 — 15_join_risk_txn.sas, 22_marketing_list.sas, 24_ops_alerts.sas).
    # Fixing it means the FIELD becomes a list: `sep_list("joins", [], ...,
    # min=0)` repeats join_clause zero or more times with NO separator token
    # (each alternative already leads with its own LEFT/INNER keyword — the
    # same "juxtaposition, no separator" shape CASE_FORM's `whens` already
    # proved for WHEN..THEN clauses). select_core's own ARITY is unchanged (6
    # args, same position); what changes is what that one arg IS — a Prolog
    # list instead of `none`/`some(J)` — which is why this is a Rust change,
    # not just a grammar one: every consumer that unwraps `some(J)` at that
    # position (lineage.rs, interp.rs, emit.rs, emit_pretty.rs — the last of
    # which also has a "zero clauses at all" fast-path check that compared the
    # field to the atom `none`, which must become "list is empty") has to walk
    # a list instead. See docs/plan for the full consumer list; task 5c's report
    # names every file touched.
    #
    # Only LEFT/INNER (both explicitly qualified — this corpus never writes a
    # bare `JOIN`) are alternatives here, and deliberately so: a bare-JOIN
    # alternative sharing the "inner_join" functor with the explicit INNER
    # alternative would make the two structurally IDENTICAL (same functor,
    # same arity, source keywords contribute no term argument), so print
    # could not tell them apart and would always emit whichever alternative
    # is listed first — silently rewriting a source `JOIN` to `INNER JOIN`
    # and breaking the source-rebuild law. Since nothing in this corpus
    # writes a bare JOIN, that alternative would be untested AND unsound, so
    # it is left out rather than added on faith.
    #
    # CROSS JOIN (17_compliance_check.sas, the one remaining fold failure
    # after this task) is still deliberately NOT one of these alternatives:
    # SAS/this corpus writes it with no ON clause at all, so it needs an
    # ARITY-1 term (cross_join(Src)) in the list, not arity-2 — every
    # consumer above reads J.args()[0]/[1] unconditionally once it sees a
    # list item, so an arity-1 item would panic, not silently misbehave.
    # Teaching those four Rust functions (and their four Prolog mirrors) to
    # branch on J's arity before indexing it is a real fix, but a separate
    # one from "the list can now hold more than one item" — out of scope
    # here; see the task 5c report.
    "join_clause": [
        rule_alt("left_join", kw("LEFT"), kw("JOIN"), rule_ref("src", "from_source"), kw("ON"), expr("on"),
                 doc="LEFT JOIN src ON e"),
        rule_alt("inner_join", kw("INNER"), kw("JOIN"), rule_ref("src", "from_source"), kw("ON"), expr("on"),
                 doc="INNER JOIN src ON e"),
    ],
    "select_core": [
        rule_alt(
            "select_core",
            kw("SELECT"), comma_list("cols", PROJ, min=1),
            kw("FROM"), rule_ref("from", "from_source"),
            sep_list("joins", [], rule_ref("j", "join_clause"), min=0),
            opt(kw("WHERE"), expr("where")),
            opt(kw("GROUP"), kw("BY"), comma_list("groupby", expr("k"), min=1)),
            opt(kw("HAVING"), expr("having")),
            doc="SELECT cols FROM src ([LEFT|INNER] JOIN src ON e)* [WHERE e] [GROUP BY e,...] [HAVING e]",
        ),
    ],
    # fix round 1 (2026-09-09): `choice(..., default="asc")` cannot round-trip. Choice's
    # print (gen_prolog.py's Choice case in compile_parts_print) emits the literal keyword
    # for whatever value the field resolved to, and the zero-token default branch resolves
    # to THE SAME value ("asc") a real `ASC` keyword would — print cannot tell "the source
    # wrote ASC" from "the source wrote nothing" once both collapse to one atom, so an
    # omitted ASC/DESC gets one injected on rebuild (`order by a` -> `order by a asc`,
    # source-rebuild law broken). No corpus statement caught this — `14_large_txn_report.sas`
    # is the corpus's only ORDER BY and always writes DESC explicitly — but the bug is
    # unconditional for a bare `ORDER BY key`, not corpus-specific; see
    # test_bare_order_by_round_trips (rust_rules_converter/tests) and the fix-round-1
    # addendum in the task 5c report. Fixed by dropping Choice's own `default=` and
    # wrapping it in `opt(...)` instead — Opt genuinely preserves presence/absence (some/
    # none), which a defaulted Choice cannot, and Group already tolerates an Opt inside its
    # parts (PROJ's own two Opts prove this). `orderby`'s 2nd field is now
    # `none|some(asc)|some(desc)` instead of a bare atom; this is a SAS-only fix — the
    # identical latent bug is copied verbatim into pipeline/specs/hive.py's own select_stmt
    # and is NOT touched here (see the task 5c report for why).
    "select_stmt": [
        rule_alt(
            "select_stmt",
            sep_list("cores", [kw("UNION"), kw("ALL")], rule_ref("core", "select_core"), min=1),
            opt(kw("ORDER"), kw("BY"),
                group("orderby", expr("key"), opt(choice("dir", {"ASC": "asc", "DESC": "desc"})))),
            opt(kw("LIMIT"), expr("n")),
            doc="select_core (UNION ALL select_core)* [ORDER BY key [ASC|DESC]] [LIMIT n] — "
                "one ORDER BY key, same as pipeline/specs/hive.py's own select_stmt",
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
    # task 5b: LENGTH var $ n ... — storage length for one or more DATA-step
    # variables; general per length_var's two alternatives (char with $, or
    # bare numeric), though every occurrence in this corpus is char.
    statement("length", kw("LENGTH"), sep_list("vars", [], rule_ref("v", "length_var"), min=1),
              doc="LENGTH var $ n [var $ n | var n ...] — declares variable storage length"),
    # task 5b: INFILE DATALINES DSD DLM='delim' TRUNCOVER — every occurrence
    # in this corpus (8 of them) is this exact fixed shape, read straight off
    # the following DATALINES block; DLM's delimiter is the one piece of
    # real data (captured through expr so its literal round-trips).
    statement("infile", kw("INFILE"), kw("DATALINES"), kw("DSD"), kw("DLM"), sym("="), expr("dlm"), kw("TRUNCOVER"),
              doc="INFILE DATALINES DSD DLM='delim' TRUNCOVER"),
    statement("datalines", raw("rows", "datalines"), doc="DATALINES; rows ;"),
    statement("set", kw("SET"), rule_ref("in", "dsname"), doc="SET lib.ds"),
    statement("subset_if", kw("IF"), expr("cond"), doc="a subsetting IF: keep the row when cond is true"),
    statement("if_then_set", kw("IF"), ident("var"), sym("="), expr("val"), kw("THEN"), kw("SET"), rule_ref("in", "dsname"),
              doc="IF _N_ = 1 THEN SET lib.ds — read one row once, its variables are retained on every output row"),
    # task 5b: a plain DATA-step assignment, `var = expr ;` — status = 'OK',
    # event_ts = datetime(), run_id = 'FD_TABLE_DEPS'. NOT built with
    # pydsl_lib's `assign=True` ("REF = <parts>") convenience: this engine's
    # own Rust side (rust_rules_converter/src/parser.rs, fold()) has
    # `if st.assign { continue; } // not used by SAS` — every assign=True
    # statement is unconditionally skipped during fold, so one would never
    # actually parse here. Writing the same shape by hand instead — a plain
    # ident() capture, a literal `=`, then expr() — reaches the exact same
    # term shape's spirit (assign(Var, Val)) through the ordinary piece path
    # that fold() does not special-case. No other statement here starts with
    # a bare WORD token, so this cannot be ambiguous with IF/SET/MERGE/etc,
    # which all start with a keyword.
    statement("assign", ident("var"), sym("="), expr("val"), doc="var = expr ; — a DATA-step variable assignment"),
    # task 5b: OUTPUT — writes the current row to the output dataset (used
    # to emit more than one row per DATA-step iteration, as 16_audit_log.sas
    # does). No lineage of its own; it just needs to fold and round-trip.
    statement("output", kw("OUTPUT"), doc="OUTPUT — writes the current PDV row"),
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
