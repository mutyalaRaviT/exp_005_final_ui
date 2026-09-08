"""pipeline.specs.pyspark — the PySpark pyDSL for exp_42's lineage loop (2026-09-07).

Why: loop 2 asks "SAS → node/4 → column lineage" to equal "PySpark → node/4 →
column lineage". The PySpark side must therefore be PARSED, by the same step
that parses SAS: this file is data, pipeline/gen_prolog.py makes its DCG
(out/grammar/pyspark.pl, parse AND print) and pipeline/export_spec.py its JSON
(out/spec/pyspark.json) for the Rust engine. Nothing here is code.

Scope: the module-level statements a PySpark job is made of — assignments,
dataset registrations, method chains over DataFrames, pyspark.sql.functions
calls, keyword arguments, lists and tuples, `for`, imports. Function bodies
(the runtime preamble) are not statements of the job and are cut off before
parsing (loops/extract_pyspark_body.py).

Python's line rule: a statement ends at a newline, except inside ( [ { —
`eos_kinds` + `bracket_pairs` below say exactly that; there is no `;`.

Term vocabulary (what node/4 holds):
    put(lit(Name), Df)                 the converter's "this dataset now exists": put("lib.ds", <chain>)
    assign(Name, Expr)                 x = expr
    set_item(Name, Key, Value)         X["k"] = v
    for_in(Var, Iter)                  for v in iter:
    expr_stmt(Expr)                    a bare call, e.g. spark.stop()
    import(Module) | from_import(Module, Name, none|some(Alias))
    Expressions: dot(Obj, Member)      obj.member — the method chain, tightest level, left-assoc
                 call(Name, [Args])    name(args)     index(Name, Key)   name[key]
                 kwarg(Name, Value)    name=value     list([...])  tuple(First, [Rest])
                 col(Name) a bare Python name, lit(V) a number or a string (kept verbatim, quotes stripped)
                 paren/1, neg/1, not/1 (~), pow, mul/div/mod, add/sub, eq/ne/lt/le/gt/ge, and (&), or (|)
"""
from pipeline.pydsl.pydsl_lib import (
    leaf, level, ladder, one_of, prefix, form,
    kw, sym, ident, expr, comma_list, opt, statement, parts_form,
)

LEAVES = [
    leaf("whitespace", r"[ \t\r]+|\\\r?\n", "whitespace"),
    leaf("newline", r"\r?\n", "newline"),
    leaf("comment", r"#[^\n]*", "comment"),
    # Python strings keep their backslash escapes verbatim (backslash_escape=False below):
    # "a\nb" folds to lit('a\nb') with the two characters, and prints back the same way.
    leaf("string_double", r'"(?:\\.|[^"\\\n])*"', "string"),
    leaf("string_single", r"'(?:\\.|[^'\\\n])*'", "string"),
    leaf("number", r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", "number"),
    leaf("word", r"[A-Za-z_][A-Za-z0-9_]*", "word"),
    leaf("multi_symbol", r"==|!=|<=|>=|\*\*|//", "symbol"),
]

KEYWORDS = ["for", "in", "import", "from", "as", "put"]

EXPR_LADDER = ladder(
    level("dot", one_of(".", functor="dot"), doc="obj.member — attribute or method call; binds tightest, left to right"),
    level("pow", one_of("**", functor="pow"), assoc="none"),
    level("unary", prefix("-", "~", functor={"-": "neg", "~": "not"}), doc="unary minus; ~ is Column NOT"),
    level("mul", one_of("*", "/", "%", functor={"*": "mul", "/": "div", "%": "mod"})),
    level("add", one_of("+", "-", functor={"+": "add", "-": "sub"})),
    level("cmp", one_of("==", "!=", "<", "<=", ">", ">=",
                        functor={"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}),
          assoc="none", doc="Column comparisons"),
    level("and", one_of("&", functor="and")),
    level("or", one_of("|", functor="or")),
)

EXPR_FORMS = [
    form("paren", "( E )", doc="a parenthesised expression"),
    form("call", "ID ( ARGS )", doc="name(args): F.col(...), filter(...), agg(...), put is a statement"),
    parts_form("index", ident("name"), sym("["), expr("key"), sym("]"), doc="name[key]: ds[\"lib.ds\"]"),
    parts_form("kwarg", ident("name"), sym("="), expr("value"), doc="keyword argument: how=\"full\""),
    parts_form("list", sym("["), comma_list("items", expr("e"), min=0), sym("]"), doc="[a, b, ...]"),
    parts_form("tuple", sym("("), expr("first"), sym(","), comma_list("rest", expr("e"), min=0), sym(")"),
               doc="(a, b, ...) — two or more items; (a) is paren"),
]

EXPR_LEAVES = [
    leaf("number", "", "lit(V)"),
    leaf("string", "", "lit(V)", doc="quotes stripped, escapes kept verbatim", dequote=True, backslash_escape=False),
    leaf("word", "", "col(V)", doc="a bare Python name"),
]

STATEMENTS = [
    statement("put", kw("put"), sym("("), expr("name"), sym(","), expr("df"), sym(")"),
              doc="put(\"lib.ds\", df) — registers a dataset; the analogue of DATA / CREATE TABLE"),
    statement("assign", ident("target"), sym("="), expr("value"), doc="x = expr"),
    statement("set_item", ident("target"), sym("["), expr("key"), sym("]"), sym("="), expr("value"), doc="X[k] = v"),
    statement("for_in", kw("for"), ident("var"), kw("in"), expr("iter"), sym(":"), doc="for v in iter:"),
    statement("from_import", kw("from"), expr("module"), kw("import"), ident("name"), opt(kw("as"), ident("alias")),
              doc="from pyspark.sql import functions as F"),
    statement("import", kw("import"), expr("module"), doc="import csv"),
    statement("expr_stmt", expr("e"), doc="a bare expression: spark.stop(), sas_print(x)"),
]

LANG = {
    "name": "pyspark",
    "ext": ".py",
    "keywords": KEYWORDS,
    "leaves": LEAVES,
    "statement_end": [],
    "eos_kinds": ["newline"],
    "bracket_pairs": [["(", ")"], ["[", "]"], ["{", "}"]],
    "ladder": EXPR_LADDER,
    "forms": EXPR_FORMS,
    "expr_leaves": EXPR_LEAVES,
    "statements": STATEMENTS,
    "rules": {},
    # block law: a `put` closes a block; the assigns (scalar subqueries) and X[k] = v lines
    # (LIBS, FORMATS) before it belong to it, so one block is one runnable step
    "blocks": {"open": [], "close": ["put"], "single": ["for_in", "import", "from_import", "expr_stmt"]},
}
