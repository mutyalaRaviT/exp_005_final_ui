"""oozie.py — Oozie workflow XML tokeniser + statement-grammar spec for
the exp_014 vertical slice.

Why this file exists: same pyDSL-only law as pig.py/hive.py — the
tokeniser engine (pipeline/tokeniser.py) and the DCG generator
(pipeline/gen_prolog.py) are language-blind; this module is the one place
that says what an Oozie workflow XML file is made of.

DECISION (owner, 2026-08-24), baked into this file on purpose: Oozie
statements really are XML ELEMENTS, not `;`-terminated lines, so there is
no natural per-statement terminator symbol the way Pig/Hive have `;`. The
simplest honest fit to the fixed 9-step pipeline (which assumes "a file is
a sequence of statements, each ending at a terminator") is to make the
WHOLE FILE one statement: `"statement_end": []`. gen_prolog.py's
gen_statements() treats an empty statement_end as "no trailing symbol to
match/print" (see its docstring) — that is the one generic-engine change
this decision required; nothing here is oozie-specific inside that file.
The grammar below folds the element TREE in one shot: `workflow(Name,
Xmlns, [Node, ...])`, where each Node is `start/1`, `end/1`, `action/4`,
`fork/2`, or `join/2` (see the `RULES["node"]` alternatives below) — the
same "fold the whole thing, print it back" discipline every other
language in this pipeline uses, just with one statement per file instead
of many.

LEXICAL SHAPE — XML is simple lexically, so the token-leaf approach still
applies directly:
    comment      <!-- ... -->                (DOTALL, one token)
    whitespace   runs of space/tab/CR/LF
    string       "..." (attribute values only; backslash-escapes anything)
    word         tag and attribute names — `[A-Za-z_][A-Za-z0-9_-]*`, the
                 one widening beyond Pig/Hive's plain `\\w*` alphabet: Oozie
                 spells its root element `workflow-app`, hyphen and all.
    symbol       everything else falls through to the engine's 1-char
                 fallback: `<`, `>`, `/`, `=` are the only ones this
                 corpus's shapes ever need.
No number leaf: every value this grammar ever captures lives inside a
quoted attribute string (paths, names, a version-ish xmlns URI), never as
a bare numeric literal, so there is nothing for a number leaf to catch.

TERM VOCABULARY — every captured value is an IDENTIFIER (a node name, a
script path, a transition target), never something to be treated as a
typed literal operand, so this grammar deliberately does NOT reuse Pig's
`lit(V)`/`col(V)` leaf shapes. It hooks a `string` token straight into a
NEW expr leaf kind, "atom" (gen_prolog.py's LEAF_PARSE/LEAF_PRINT, the one
generator addition this file needed): a dequoted string becomes a BARE
Prolog atom, no wrapper. `to="X"` transitions are wrapped one level
further, via a Group, into `to(Atom)` — exactly the "ok/error transitions
as to(atom) fields" shape from the phase spec:
    workflow(Name, Xmlns, [Node, ...])
    start(To)                                <start to="X"/>
    end(Name)                                <end name="X"/>
    action(Name, Body, to(OkTo), to(ErrTo))  <action name="X">BODY
                                              <ok to=.."/><error to=.."/></action>
    fork(Name, [path(Start), ...])           <fork name="X">path*</fork>
    join(Name, To)                           <join name="X" to="Y"/>
    path(Start)                              <path start="X"/>
Body (the `action_body` rule, an EITHER/OR same discipline as `forms`):
    shell(ExecPath)                          <shell exec="path"/>
    pig(ScriptPath)                          <pig script="path"/>
"""
from pipeline.pydsl.pydsl_lib import (
    leaf, level, ladder, kw, sym, expr, group, sep_list,
    rule_alt, rule_ref, statement,
)

# ---- expression ladder: Oozie attribute values carry no operators at all
# (no arithmetic, no comparisons) — expr(E) reduces straight through one
# no-op level to the "atom" leaf below. A ladder needs at least one level
# (gen_ladder reads ladder[-1] as the entry point), so this is the
# smallest legal one: zero ops, which gen_prolog.py's is_prefix check
# treats (vacuously, `all([])`) as a pure passthrough.
EXPR_LADDER = ladder(
    level("flat", [], doc="no operators — expr(E) is just the atom leaf"),
)
EXPR_FORMS = []
EXPR_LEAVES = [
    leaf("atom", "", "A", doc="a dequoted XML attribute string -> a bare "
         "Prolog atom (never lit()); see gen_prolog.py's LEAF_PARSE/LEAF_PRINT "
         "\"atom\" entries for the one generator addition this needed"),
]

# ---- one small helper per repeated shape, so each call site builds its
# OWN Group object — Aux (pipeline/gen_prolog.py) keys a Group's generated
# nonterminal name by Python id(), so two call sites sharing one Group
# instance would alias to the same generated name; two structurally
# identical but DISTINCT objects avoid that trap cleanly.

def _to():
    return group("to", kw("to"), sym("="), expr("v"),
                  doc='an ok/error transition target: to="node" -> to(Atom)')


def _path():
    return group("path", sym("<"), kw("path"), kw("start"), sym("="), expr("start"),
                  sym("/"), sym(">"),
                  doc='one <path start="alias"/> branch inside a <fork>')


RULES = {
    "action_body": [
        rule_alt("shell", sym("<"), kw("shell"), kw("exec"), sym("="), expr("exec"),
                 sym("/"), sym(">"),
                 doc='<shell exec="path"/> -> shell(Path)'),
        rule_alt("pig", sym("<"), kw("pig"), kw("script"), sym("="), expr("script"),
                 sym("/"), sym(">"),
                 doc='<pig script="path"/> -> pig(Path)'),
    ],
    "node": [
        rule_alt("start", sym("<"), kw("start"), kw("to"), sym("="), expr("to"),
                 sym("/"), sym(">"),
                 doc='<start to="node"/> -> start(To)'),
        rule_alt("end", sym("<"), kw("end"), kw("name"), sym("="), expr("name"),
                 sym("/"), sym(">"),
                 doc='<end name="node"/> -> end(Name)'),
        rule_alt("action",
                 sym("<"), kw("action"), kw("name"), sym("="), expr("name"), sym(">"),
                 rule_ref("body", "action_body"),
                 sym("<"), kw("ok"), _to(), sym("/"), sym(">"),
                 sym("<"), kw("error"), _to(), sym("/"), sym(">"),
                 sym("<"), sym("/"), kw("action"), sym(">"),
                 doc='<action name="n">BODY<ok to=../><error to=../></action> '
                     '-> action(Name, Body, to(Ok), to(Err))'),
        rule_alt("fork",
                 sym("<"), kw("fork"), kw("name"), sym("="), expr("name"), sym(">"),
                 sep_list("paths", [], _path(), min=2),
                 sym("<"), sym("/"), kw("fork"), sym(">"),
                 doc='<fork name="n">path,path,...</fork> -> fork(Name, [path(...), ...])'),
        rule_alt("join", sym("<"), kw("join"), kw("name"), sym("="), expr("name"),
                 kw("to"), sym("="), expr("to"), sym("/"), sym(">"),
                 doc='<join name="n" to="m"/> -> join(Name, To)'),
    ],
}

# ---- statements: EXACTLY the shape corpus/oozie/small/*.xml uses — one
# workflow-app root element per file, and the whole file IS the statement
# (see the module docstring's DECISION for `statement_end: []`).
STATEMENTS = [
    statement("workflow",
              sym("<"), kw("workflow-app"),
              kw("name"), sym("="), expr("name"),
              kw("xmlns"), sym("="), expr("xmlns"),
              sym(">"),
              sep_list("nodes", [], rule_ref("n", "node"), min=1),
              sym("<"), sym("/"), kw("workflow-app"), sym(">"),
              assign=False,
              doc="the whole file, one <workflow-app> element: "
                  "workflow(Name, Xmlns, [Node, ...])"),
]

LANG = {
    "name": "oozie",
    "ext": ".xml",
    "keywords": [
        "workflow-app", "start", "end", "action", "shell", "pig", "exec",
        "script", "ok", "error", "to", "fork", "join", "path", "name", "xmlns",
    ],
    "leaves": [
        # XML comments: `<!-- ... -->`, DOTALL so one can span lines; tried
        # first so a `<!--` is never mistaken for the bare `<` symbol.
        leaf("comment", r"(?s)<!--.*?-->", "comment"),
        # whitespace: runs of spaces/tabs/CR/LF, one token per run.
        leaf("whitespace", r"[ \t\r\n]+", "whitespace"),
        # strings: double-quoted attribute values, backslash-escapes anything.
        leaf("string", r'"(?:\\.|[^"\\])*"', "string"),
        # words: tag/attribute names — hyphen included for `workflow-app`
        # (keyword-ness decided by the engine casefolding against
        # LANG["keywords"], not here).
        leaf("word", r"[A-Za-z_][A-Za-z0-9_-]*", "word"),
    ],
    # No per-statement terminator — see the module docstring's DECISION.
    "statement_end": [],
    "ladder": EXPR_LADDER,
    "forms": EXPR_FORMS,
    "expr_leaves": EXPR_LEAVES,
    "statements": STATEMENTS,
    "rules": RULES,
}
