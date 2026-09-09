"""sqoop.py — Sqoop CLI tokeniser + statement-grammar spec for the exp_014
Hadoop vertical slice (SQOOP lane).

Why this file exists: same contract as pipeline/specs/pig.py and
pipeline/specs/hive.py — the tokeniser engine (pipeline/tokeniser.py) and
the DCG generator (pipeline/gen_prolog.py) are both language-blind; this
module is the ONE place that says what a Sqoop `import`/`export` CLI
invocation is made of.

WHAT A SQOOP FILE LOOKS LIKE (corpus/sqoop/small/*.sqoop): a single copy-
pasted shell invocation, one `sqoop import|export` command, its
`--long-option [value]` flags one per continuation line, backslash-newline
line-continued the way a person would actually paste it out of a runbook:

    sqoop import \
      --connect 'jdbc:mysql://dbhost:3306/salesdb' \
      --table customers \
      --target-dir '/user/hadoop/customers' \
      --fields-terminated-by ',' ;

The trailing `;` is this DSL's own statement terminator (same role as
Pig's/Hive's `;` — the engine's EOS marker and the generated grammar's
own required trailing symbol both key off `LANG["statement_end"]`), not
part of real Sqoop shell syntax; every corpus file ends with one.

ORDER MATTERS (see pig.py's docstring for the general rule: first leaf
whose regex matches at the current offset wins). A backslash-newline
continuation must be recognised before the generic whitespace leaf ever
gets a look (it isn't — `\` isn't in `[ \t\r\n]+` — but it is placed
first anyway, right where the reader expects the "this row is whitespace
too" rule). A `--long-option` flag must be recognised as ONE token before
the generic word leaf gets a chance to prove it wouldn't have matched
anyway (the leading `-` isn't a word character either) — same "make the
intent visible even where it's not load-bearing" reasoning.

Keyword set: `sqoop` (the literal command name every corpus file starts
with — it contributes zero term arguments, same as any other bare kw()),
plus `import`/`export` (the two subcommands `choice()` below dispatches
on). Every `--flag` name is deliberately NOT a keyword — it tokenises as
an ordinary WORD (via the `opt_flag` leaf below), same as a Pig/Hive
identifier, so `ident()` can capture it as-is into the term.

Term vocabulary:
    cmd(import|export, [opt(Name, none|some(Value)), ...])
        the whole statement — Name is the flag's own source text
        ('--connect', '--table', '--hive-import', ...) as a bare atom;
        Value is none for a boolean flag with no following value
        (--hive-import) and some(V) otherwise, V a col(Atom) (bare
        word — a table/column name like `customers` or `id`) or a
        lit(V) (a quoted string, dequoted, or a real number)
"""
from pipeline.pydsl.pydsl_lib import (
    leaf, level, ladder, one_of,
    kw, ident, expr, group, sep_list, choice, opt, statement,
)

# ---------------------------------------------------------------------------
# expression ladder — sqoop option VALUES are always a single atom (a bare
# word like a table/column name, a quoted string like a JDBC URL or a
# delimiter, or a number like --num-mappers 4). No operator ever combines
# two values in this corpus, so the ladder is one no-op level: it exists
# only so `expr()` (option values, below) has somewhere to route through,
# same "expr hooks the ladder" contract pig.py/hive.py both use.
EXPR_LADDER = ladder(
    level("atom", one_of(), doc="sqoop option values are plain atoms — no infix/prefix operator is ever needed"),
)
EXPR_FORMS = []  # no call()/qualified-column/positional shapes in this corpus
EXPR_LEAVES = [
    leaf("number", "", "lit(V)", doc="a NUMBER token folds to a real Prolog number, e.g. --num-mappers 4"),
    leaf("string", "", "lit(V)", doc="a STRING token, quotes stripped, e.g. --connect 'jdbc:...'", dequote=True),
    leaf("word", "", "col(V)", doc="a bare WORD token used as a plain identifier value, e.g. --table customers"),
]

# ---------------------------------------------------------------------------
# statement: EXACTLY the shape corpus/sqoop/small/*.sqoop uses — one
# `sqoop import|export --flag [value] --flag [value] ...` invocation.
OPT = group(
    "opt", ident("name"), opt(expr("value")),
    doc="one --flag [value] pair; value is none for a bare boolean flag like --hive-import",
)

STATEMENTS = [
    statement(
        "cmd", kw("SQOOP"),
        choice("kind", {"IMPORT": "import", "EXPORT": "export"}),
        sep_list("opts", [], OPT, min=1),
        assign=False,
        doc="sqoop import|export --flag [value] --flag [value] ... ; "
            "no separator token between options — they just run together, "
            "same juxtaposition discipline hive.py's CASE WHEN..THEN uses",
    ),
]

LANG = {
    "name": "sqoop",
    "ext": ".sqoop",
    "keywords": ["sqoop", "import", "export"],
    "leaves": [
        # a backslash immediately before a newline is a shell line
        # continuation — treated as whitespace, not as a symbol, so the
        # continued command still tokenises as ONE statement's worth of
        # tokens. Must NOT have trailing spaces after the backslash in the
        # corpus source (that would leave a bare `\` to fall through to
        # the engine's 1-char symbol fallback instead).
        leaf("line_cont", r"\\\n", "whitespace"),
        # comments: `#` to end of line — Sqoop's own --options-file format
        # documents `#`-prefixed lines as comments (2026-08-26 addition;
        # see pipeline/comments.py — this was the one language with no
        # comment leaf at all, so a `#` in a real .sqoop file would
        # previously have fallen through to the engine's 1-char symbol
        # fallback and broken the fold). Must come before "whitespace" so
        # `#` is never mistaken for anything else, though nothing else in
        # this leaf list starts with `#` regardless.
        leaf("comment", r"#[^\n]*", "comment"),
        # whitespace: runs of spaces/tabs/CR/LF, one token per run.
        leaf("whitespace", r"[ \t\r\n]+", "whitespace"),
        # strings: single-quoted, backslash-escapes anything incl. `\'`.
        leaf("string", r"'(?:\\.|[^'\\])*'", "string"),
        # a --long-option flag tokenises as ONE word token, whole — e.g.
        # --connect, --fields-terminated-by, --hive-import — tried before
        # the generic word leaf so the flag's own dashes are never split
        # into bare 1-char symbol tokens.
        leaf("opt_flag", r"--[a-z-]+", "word"),
        # numbers: ints and decimals — `4`, `0.5`.
        leaf("number", r"\d+(?:\.\d+)?", "number"),
        # words: plain identifiers and keywords (keyword-ness is decided by
        # the engine casefolding against LANG["keywords"], not here).
        leaf("word", r"[A-Za-z_][A-Za-z0-9_]*", "word"),
    ],
    "statement_end": [";"],
    # Phase C (pipeline/gen_prolog.py reads these; pipeline/tokeniser.py never does):
    "ladder": EXPR_LADDER,
    "forms": EXPR_FORMS,
    "expr_leaves": EXPR_LEAVES,
    "statements": STATEMENTS,
}
