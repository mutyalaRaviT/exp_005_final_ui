"""pipeline.gen_prolog — compiles pipeline/specs/<lang>.py's declarative
`ladder`/`forms`/`expr_leaves`/`statements` into out/grammar/<lang>.pl:
a DCG `stmt//1` (parse, SWI-compiles to stmt/3) and a plain predicate
`print_stmt/2` (print), both directions generated from the same data.

This is the GENERATOR half of the pyDSL-only law (owner, 2026-08-24): every
statement shape and every operator lives as data in pipeline/specs/<lang>.py
(pipeline/pydsl/pydsl_lib.py's KW/SYM/Cap/Group/CommaList/Choice/Opt/
Statement/Level/Op/Leaf/Form). This file knows only that FINITE, generic
vocabulary — never a keyword, never a statement shape, never a language name.
The one language-shaped-looking exception is `LANG["forms"]`'s five shape
STRINGS ("( E )", "ID ( ARGS )", "ID . ID", "ID :: ID", "$ NUM", "KW <word>")
— a fixed small grammar of shapes, the same discipline exp_013's gen.py
already used for SAS forms, not a per-language special case.

Run: python3 -m pipeline.gen_prolog <lang>   (writes out/grammar/<lang>.pl)
"""
import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def is_word(s):
    """True for a spelling that tokenises as one WORD/KEYWORD token — the
    generic engine's own word alphabet, `[A-Za-z_]\\w*`, widened with `-`
    on top: exp_014's XML lane (pipeline/specs/oozie.py) has tag/attribute
    names like `workflow-app` that are still ONE token by that spec's own
    word leaf (`[A-Za-z_][A-Za-z0-9_-]*`), so the KW-vs-SYM decision here
    has to recognise the same alphabet or a hyphenated keyword would be
    generated as a bogus multi-char symbol match. Pig/Hive spellings never
    contain `-`, so this is a pure widening — no existing kw()/one_of()
    spelling changes classification."""
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", s) is not None


def plq(s):
    """Render `s` as a Prolog-quoted atom literal in GENERATED source text.
    Quoting an already-safe atom is still legal Prolog, so this never has
    to decide whether `s` "needs" quoting."""
    return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"


class Ctr:
    """One counter per grammar, so every generated variable/nonterminal
    name is unique — reused across Group/CommaList/Opt without collisions."""

    def __init__(self):
        self.n = 0

    def next(self, prefix="V"):
        self.n += 1
        return f"{prefix}{self.n}"


def match_kw_or_sym(spelling, var):
    """DCG match for one operator/keyword spelling: case-insensitive
    keyword (kw()'s documented convention: canonical print is lowercased
    `text`, so the DOWNCASED source token must equal the LOWERCASED
    spelling — kw("FILTER") still has to match a source token 'FILTER')
    or a literal symbol."""
    if is_word(spelling):
        return f"[tok(keyword,{var})], {{ downcase_atom({var},{plq(spelling.lower())}) }}"
    return f"[tok(symbol,{plq(spelling)})]"


# =============================================================== expr ladder
# Turns LANG["ladder"] (tightest level first) + LANG["forms"] + LANG["expr_leaves"]
# into: expr//1, one lvl_<name>//1 per level, prim//1, args//1 (parse); and
# print_expr/3, expr_own/3, level_prec/2, print_args/2 (print). Every level,
# form and leaf is read from that data — nothing here names a language.

def gen_ladder(ladder, forms, expr_leaves, ctr, aux):
    lines, plines = [], []
    n = len(ladder)
    prec = {lv.name: (n - i) * 10 for i, lv in enumerate(ladder)}

    loosest = ladder[-1].name  # ladder() is tightest-first; expr enters loosest
    lines.append(f"expr(E) --> lvl_{loosest}(E).")
    lines.append("")

    tighter = "prim"
    for lv in ladder:
        L, T = f"lvl_{lv.name}", tighter
        is_prefix = all(o.kind == "prefix" for o in lv.ops)
        lines.append(f"% level {lv.name}" + (f" — {lv.doc}" if lv.doc else ""))
        if is_prefix:
            for op in lv.ops:
                lines.append(f"{L}({op.functor}(E)) --> {match_kw_or_sym(op.spelling, 'K')}, {L}(E).")
            lines.append(f"{L}(E) --> {T}(E).")
        elif lv.assoc == "left":
            # loop style: accumulator, right-recursive on the remainder —
            # safe under plain top-down parsing, no left recursion.
            lines.append(f"{L}(E) --> {T}(L0), {L}_rest(L0, E).")
            for op in lv.ops:
                lines.append(f"{L}_rest(L0, E) --> {match_kw_or_sym(op.spelling, 'K')}, {T}(R), {L}_rest({op.functor}(L0,R), E).")
            lines.append(f"{L}_rest(E, E) --> [].")
        else:  # assoc="none" — one shot, no chaining; both sides from T
            for op in lv.ops:
                if op.kind == "list_rhs":
                    # right side is "( e, e, ... )" — Hive's `x IN (a, b)`
                    lines.append(
                        f"{L}({op.functor}(A,B)) --> {T}(A), {match_kw_or_sym(op.spelling, 'K')}, "
                        f"[tok(symbol,'(')], args(B), [tok(symbol,')')]."
                    )
                else:
                    lines.append(f"{L}({op.functor}(A,B)) --> {T}(A), {match_kw_or_sym(op.spelling, 'K')}, {T}(B).")
            lines.append(f"{L}(E) --> {T}(E).")
        lines.append("")
        tighter = L

    lines.append("% forms — tried before the bare leaves so a call/qcol/positional")
    lines.append("% prefix is matched whole; Prolog backtracking makes the try-then-")
    lines.append("% fall-through safe (no lookahead needed).")
    # Both directions are generated from this same `forms` list, but a
    # shape-string form may deliberately contribute a parse clause and NO
    # print clause (Pig's "ID . ID", whose "ID :: ID" sibling owns the
    # canonical print). These two sets let generate() prove that every
    # parse-side functor is still printable by SOME sibling — see
    # check_every_parsed_form_can_print() below.
    parse_form_functors, print_form_functors = set(), set()
    for f in forms:
        fkind = type(f).__name__
        if fkind == "PartsForm":
            for goals, args in compile_parts_parse(f.parts, ctr, aux):
                term = f"{f.name}({','.join(args)})" if args else f.name
                body = ", ".join(goals) if goals else "[]"
                lines.append(f"prim({term}) --> {body}.")
        elif fkind == "RuleForm":
            lines.append(f"prim({f.name}(V)) --> [tok(symbol,'(')], rule_{f.rule_name}(V), [tok(symbol,')')].")
        else:
            parse_form_functors.add(_form_functor(f))
            lines.append(_form_parse_clause(f))
    lines.append("")
    lines.append("% leaves — token kind == leaf name, by convention (see pydsl_lib.leaf)")
    for lf in expr_leaves:
        lines.append(_leaf_parse_clause(lf))
    lines.append("")
    lines += [
        "args([A|As]) --> expr(A), args_rest(As).",
        "args([]) --> [].",
        "args_rest([A|As]) --> [tok(symbol,',')], expr(A), args_rest(As).",
        "args_rest([]) --> [].",
    ]

    # ---- print direction: print_expr/3 wraps expr_own/3 in minimal parens ----
    plines.append("% precedence table: tightest level highest number")
    for name, p in prec.items():
        plines.append(f"level_prec({plq(name)}, {p}).")
    plines += [
        "",
        "print_expr(Term, MinPrec, Texts) :-",
        "    expr_own(Term, OwnPrec, Inner),",
        "    ( OwnPrec >= MinPrec -> Texts = Inner",
        "    ; flatten([['('], Inner, [')']], Texts) ).",
        "",
    ]
    for lv in ladder:
        is_prefix = all(o.kind == "prefix" for o in lv.ops)
        for op in lv.ops:
            text = f"[{plq(op.spelling.lower() if is_word(op.spelling) else op.spelling)}]"
            if is_prefix:
                plines.append(
                    f"expr_own({op.functor}(A), P, Texts) :- level_prec({plq(lv.name)}, P), "
                    f"print_expr(A, P, TA), flatten([{text}, TA], Texts)."
                )
            elif lv.assoc == "left":
                plines.append(
                    f"expr_own({op.functor}(A,B), P, Texts) :- level_prec({plq(lv.name)}, P), "
                    f"print_expr(A, P, TA), P1 is P+1, print_expr(B, P1, TB), "
                    f"flatten([TA, {text}, TB], Texts)."
                )
            elif op.kind == "list_rhs":
                plines.append(
                    f"expr_own({op.functor}(A,B), P, Texts) :- level_prec({plq(lv.name)}, P), "
                    f"P1 is P+1, print_expr(A, P1, TA), print_args(B, TB), "
                    f"flatten([TA, {text}, ['('], TB, [')']], Texts)."
                )
            else:
                plines.append(
                    f"expr_own({op.functor}(A,B), P, Texts) :- level_prec({plq(lv.name)}, P), "
                    f"P1 is P+1, print_expr(A, P1, TA), print_expr(B, P1, TB), "
                    f"flatten([TA, {text}, TB], Texts)."
                )
    plines.append("")
    plines.append("% forms (print) — precedence 100: atomic, never need outer parens")
    for f in forms:
        fkind = type(f).__name__
        if fkind == "PartsForm":
            for subgoals, frag_pairs in compile_parts_print(f.parts, ctr, aux):
                pattern_args = [pv for pv, _fr in frag_pairs if pv is not None]
                term_pat = f"{f.name}({','.join(pattern_args)})" if pattern_args else f.name
                frags = [fr for _pv, fr in frag_pairs]
                t_out = ctr.next("T")
                goals = list(subgoals)
                goals.append(f"flatten([{', '.join(frags)}], {t_out})" if frags else f"{t_out}=[]")
                plines.append(f"expr_own({term_pat}, 100, {t_out}) :- {', '.join(goals)}.")
        elif fkind == "RuleForm":
            plines.append(
                f"expr_own({f.name}(V), 100, Texts) :- print_rule_{f.rule_name}(V, Inner), "
                f"flatten([['('], Inner, [')']], Texts)."
            )
        else:
            line = _form_print_clause(f)
            if line:
                print_form_functors.add(_form_functor(f))
                plines.append(line)
    check_every_parsed_form_can_print(parse_form_functors, print_form_functors)
    plines.append("")
    plines.append("% leaves (print)")
    for lf in expr_leaves:
        plines.append(LEAF_PRINT[lf.name](lf))
    plines += [
        "",
        "print_args([], []).",
        "print_args([A], Texts) :- !, print_expr(A, 0, Texts).",
        "print_args([A|As], Texts) :- print_expr(A, 0, TA), print_args(As, TAs), flatten([TA, [','], TAs], Texts).",
    ]
    return lines, plines


# The one place that says which Prolog functor+arity each shape STRING
# builds. Both _form_parse_clause and _form_print_clause below build their
# clause heads for that same functor, so this is what lets generate() check
# the two directions against each other instead of trusting them.
FORM_FUNCTOR_ARITY = {
    "( E )": 1,
    "ID ( ARGS )": 2,
    "ID . ID": 2,
    "ID . ID (canonical)": 2,
    "ID :: ID": 2,
    "$ NUM": 1,
    "$ ID": 1,
}


def _form_functor(f):
    """-> (functor_name, arity) for one shape-string form."""
    if f.shape.startswith("KW "):
        return (f.shape.split(" ", 1)[1], 0)
    if f.shape not in FORM_FUNCTOR_ARITY:
        sys.exit(f"gen_prolog: unknown form shape {f.shape!r}")
    return (f.name, FORM_FUNCTOR_ARITY[f.shape])


def check_every_parsed_form_can_print(parse_functors, print_functors):
    """The two-directions law, enforced at GENERATE time.

    A shape-string form may print-abstain on purpose: Pig declares `col`
    twice, once as "ID . ID" and once as "ID :: ID", and only the "::"
    spelling is canonical, so "ID . ID" contributes no print clause. That
    is legal ONLY because a sibling form builds the same functor/arity and
    does print it.

    Without this check, a spec that declared just "ID . ID" would generate
    a grammar that PARSES `a.b` into col/2 and can never print it again:
    the print-retokenise-refold fixpoint would fail at run time with a bare
    printfailed(Seq) and nothing would point back at the spec. Fail loudly
    here instead."""
    orphans = sorted(parse_functors - print_functors)
    if orphans:
        listed = ", ".join(f"{name}/{arity}" for name, arity in orphans)
        sys.exit(
            f"gen_prolog: form(s) {listed} can be PARSED but never PRINTED — "
            f"every form functor needs at least one form whose shape "
            f"contributes a print clause (see _form_print_clause)"
        )


def _form_parse_clause(f):
    shape = f.shape
    if shape == "( E )":
        return f"prim({f.name}(E)) --> [tok(symbol,'(')], expr(E), [tok(symbol,')')]."
    if shape == "ID ( ARGS )":
        # N may arrive as tok(word,_) OR tok(keyword,_) — Hive's COALESCE
        # is a keyword (unlike its COUNT/SUM/AVG siblings, which aren't),
        # so a call name must accept either kind; harmless for Pig, whose
        # UDF names are deliberately never keywords (see pig.py's own
        # docstring), so this never opens a new match there.
        return f"prim({f.name}(N,Args)) --> ( [tok(word,N)] ; [tok(keyword,N)] ), [tok(symbol,'(')], args(Args), [tok(symbol,')')]."
    if shape in ("ID . ID", "ID . ID (canonical)"):
        return f"prim({f.name}(N,F)) --> [tok(word,N)], [tok(symbol,'.')], [tok(word,F)]."
    if shape == "ID :: ID":
        return f"prim({f.name}(N,F)) --> [tok(word,N)], [tok(symbol,'::')], [tok(word,F)]."
    if shape == "$ NUM":
        return f"prim({f.name}(N)) --> [tok(symbol,'$')], [tok(number,V)], {{ atom_number(V,N) }}."
    if shape == "$ ID":
        # word OR keyword, same reasoning as "ID ( ARGS )" above: the name
        # after `$` can coincidentally spell a reserved word elsewhere in
        # this same grammar (e.g. Pig's `parallel $PARALLEL` — "parallel"
        # is also a keyword spelling used bare in COGROUP/JOIN), which
        # tokenises as tok(keyword,_), not tok(word,_).
        return f"prim({f.name}(N)) --> [tok(symbol,'$')], ( [tok(word,N)] ; [tok(keyword,N)] )."
    if shape.startswith("KW "):
        word = shape.split(" ", 1)[1]
        return f"prim({word}) --> [tok(keyword,K)], {{ downcase_atom(K,{plq(word)}) }}."
    sys.exit(f"gen_prolog: unknown form shape {shape!r}")


# "ID . ID" and "ID :: ID" both build the same functor/2 (a qualified column
# read two ways in Pig source); the print side only needs to emit it once,
# in its one canonical spelling (::) — so "ID . ID" contributes no print
# clause of its own.
def _form_print_clause(f):
    shape = f.shape
    if shape == "( E )":
        return f"expr_own({f.name}(E), 100, Texts) :- print_expr(E, 0, Inner), flatten([['('], Inner, [')']], Texts)."
    if shape == "ID ( ARGS )":
        return (f"expr_own({f.name}(N,Args), 100, Texts) :- print_args(Args, ArgsT), "
                f"flatten([[N], ['('], ArgsT, [')']], Texts).")
    if shape == "ID . ID":
        return None
    if shape == "ID . ID (canonical)":
        # Hive has no "::" alternative spelling — "." IS the canonical
        # print, unlike Pig's plain "ID . ID" above which stays print-
        # silent on purpose (Pig's "ID :: ID" form owns the print side).
        return f"expr_own({f.name}(N,F), 100, Texts) :- flatten([[N], ['.'], [F]], Texts)."
    if shape == "ID :: ID":
        return f"expr_own({f.name}(N,F), 100, Texts) :- flatten([[N], ['::'], [F]], Texts)."
    if shape == "$ NUM":
        return f"expr_own({f.name}(N), 100, Texts) :- format(atom(NT), '~w', [N]), flatten([['$'], [NT]], Texts)."
    if shape == "$ ID":
        return f"expr_own({f.name}(N), 100, Texts) :- flatten([['$'], [N]], Texts)."
    if shape.startswith("KW "):
        word = shape.split(" ", 1)[1]
        return f"expr_own({word}, 100, [{plq(word)}])."
    sys.exit(f"gen_prolog: unknown form shape {shape!r}")


# Leaf name == token kind, by convention (pydsl_lib.leaf's `name` doubles as
# the tokeniser kind it reads: "number" | "string" | "word"). "atom" is the
# one deliberate exception: it still reads a tok(string,_) token (exp_014's
# XML lane has no bare-word attribute values, only quoted ones), but it
# builds the BARE dequoted atom itself — no lit()/col() wrapper — because
# every value oozie.py captures through it (a node name, a script path, a
# transition target) is an identifier, never something a downstream
# consumer should treat as a literal-typed operand.
# Both LEAF_PARSE and LEAF_PRINT map leaf NAME -> a function of the actual
# Leaf object (not a bare string) since "string" and "atom" (2026-08-26 fix)
# need per-instance data — lf.double_delim — to pick the right
# unquote_escaped/quote_escaped call; the others ignore lf and return a
# fixed clause exactly as before.
def _leaf_parse_string(lf):
    dd = "true" if lf.double_delim else "false"
    if not lf.backslash_escape:  # exp_42: SAS — the doubled delimiter is the only escape
        return "prim(lit(S)) --> [tok(string,V)], { unquote_plain(V, S) }."
    return (f"prim(lit(S)) --> [tok(string,V)], "
            f"{{ unquote_escaped({dd}, V, S), "
            f"warn_if_escape_not_reversible({dd}, 0''', S, string) }}.")


def _leaf_parse_atom(lf):
    dd = "true" if lf.double_delim else "false"
    return (f"prim(A) --> [tok(string,V)], "
            f"{{ unquote_escaped({dd}, V, A), "
            f"warn_if_escape_not_reversible({dd}, 0'\\\", A, atom) }}.")


# M3a (2026-09-10), defect 1: a NUMBER leaf that sets keep_lexeme=True folds
# to lit(Value, Text) — the folded number AND the token text it came from.
# `0.40` and `0.4` are the same Prolog number, so a printer that only has the
# number can only write `0.4` and the SAS source is not reproduced byte for
# byte (corpus/team_finance/sas/raw/13_risk_flags.sas). The second argument is
# never read by arithmetic; it exists only so print_stmt can write back what
# was read. Off by default: lit/1 stays the term shape for every language that
# has not opted in (Pig/Hive/Oozie/Sqoop), so their grammars do not change.
def _leaf_parse_number(lf):
    if lf.keep_lexeme:
        return "prim(lit(N, V)) --> [tok(number,V)], { atom_number(V,N) }."
    return "prim(lit(N)) --> [tok(number,V)], { atom_number(V,N) }."


def _leaf_print_number(lf):
    if lf.keep_lexeme:
        return "expr_own(lit(N, T), 100, [T]) :- number(N), !."
    return "expr_own(lit(N), 100, [NT]) :- number(N), !, format(atom(NT), '~w', [N])."


LEAF_PARSE = {
    "number": _leaf_parse_number,
    "string": _leaf_parse_string,
    "word": lambda lf: "prim(col(N)) --> [tok(word,N)].",
    "atom": _leaf_parse_atom,
    # "path": an unquoted resource path (a REGISTER argument like
    # ./tutorial.jar) — verbatim token text, no quote-stripping, wrapped
    # in resource(V) so it is never confused with a column reference
    # (col/1, from the "word" leaf) or a string literal (lit/1).
    "path": lambda lf: "prim(resource(N)) --> [tok(path,N)].",
}
LEAF_PRINT = {
    "number": _leaf_print_number,
    "string": lambda lf: ("expr_own(lit(S), 100, [QT]) :- atom(S), \\+ number(S), quote_plain(0''', S, QT)." if not lf.backslash_escape else "expr_own(lit(S), 100, [QT]) :- atom(S), \\+ number(S), quote_escaped(0''', S, QT)."),
    "word": lambda lf: "expr_own(col(N), 100, [N]) :- atom(N).",
    "atom": lambda lf: "expr_own(A, 100, [QT]) :- atom(A), quote_escaped(0'\\\", A, QT).",
    "path": lambda lf: "expr_own(resource(N), 100, [N]) :- atom(N).",
}


def _leaf_parse_clause(lf):
    if lf.name not in LEAF_PARSE:
        sys.exit(f"gen_prolog: unknown expr leaf {lf.name!r} (token kind must be number/string/word)")
    return LEAF_PARSE[lf.name](lf)


# DEQUOTE-FLAG LAW (2026-08-26, proposal A5): dequote=True only ever meant
# anything for leaves named "string"/"atom" — those are the only two names
# LEAF_PARSE routes through a dequoting call at all. A leaf of any other
# name setting dequote=True was previously silent, decorative data: read
# by nothing, doing nothing. Catch that at GENERATE time, same shape as
# check_every_parsed_form_can_print above — a spec author's mistake should
# fail loudly, pointing at the spec, not sit as a comment nobody reads.
def check_dequote_flag_is_meaningful(expr_leaves, lang):
    for lf in expr_leaves:
        if lf.dequote and lf.name not in ("string", "atom"):
            sys.exit(
                f"gen_prolog: pipeline/specs/{lang}.py declares dequote=True on "
                f"leaf {lf.name!r}, but only \"string\"/\"atom\" leaves are ever "
                f"dequoted — this flag would be silently ignored"
            )


# ============================================================== statements
# Compiles one parts sequence (a Statement's, a Group's, or one comma_list
# item's) into one or more alternatives — more than one only when the
# sequence contains an Opt (present/absent), which is why Opt is capped at
# one per sequence (see pydsl_lib.Opt's docstring).

def compile_parts_parse(parts, ctr, aux):
    """-> list of (goals: list[str], args: list[str])."""
    alts = [([], [])]
    for part in parts:
        piece_alts = _piece_parse(part, ctr, aux)
        alts = [(g0 + g1, a0 + a1) for g0, a0 in alts for g1, a1 in piece_alts]
    return alts


def _piece_parse(part, ctr, aux):
    """-> list of (goals, args) for ONE piece; args has 0 or 1 entries."""
    kind = type(part).__name__
    if kind == "KW":
        return [([match_kw_or_sym(part.text, ctr.next("K"))], [])]
    if kind == "SYM":
        return [([f"[tok(symbol,{plq(part.text)})]"], [])]
    if kind == "Cap":
        v = ctr.next(part.field.capitalize() or "V")
        if part.kind == "ref":
            return [([f"[tok(word,{v})]"], [f"rel({v})"])]
        if part.kind == "ident":
            return [([f"[tok(word,{v})]"], [v])]
        if part.kind == "typename":
            return [([f"( [tok(word,{v})] ; [tok(keyword,{v})] )"], [v])]
        if part.kind == "expr":
            return [([f"expr({v})"], [v])]
        if part.kind.startswith("raw:"):
            tk = part.kind[4:]
            r = ctr.next("R")
            return [([f"[tok({tk},{r})]", f"{{ raw_body({r}, {v}) }}"], [v])]
        sys.exit(f"gen_prolog: unknown Cap kind {part.kind!r}")
    if kind == "RuleRef":
        v = ctr.next(part.field.capitalize() or "V")
        return [([f"rule_{part.name}({v})"], [v])]
    if kind == "Group":
        name = aux.emit_group(part, ctr)
        v = ctr.next("G")
        return [([f"{name}({v})"], [v])]
    if kind == "CommaList":
        name = aux.emit_comma_list(part, ctr)
        v = ctr.next("L")
        return [([f"{name}({v})"], [v])]
    if kind == "Choice":
        v = ctr.next("C")
        branches = []
        for src, val in part.options.items():
            branches.append(f"( {match_kw_or_sym(src, ctr.next('K'))}, {{ {v}={val} }} )")
        if part.default is not None:
            branches.append(f"( {{ {v}={part.default} }} )")
        # wrapped in one outer ( ; ) so this splices into the surrounding
        # comma-conjunction as ONE goal — Prolog's `,` binds tighter than
        # `;`, so an unwrapped "A, B ; C ; D, E" would split the WHOLE
        # clause body at top level instead of staying scoped to this piece.
        return [([f"( {' ; '.join(branches)} )"], [v])]
    if kind == "Opt":
        inner_alts = compile_parts_parse(part.parts, ctr, aux)
        if len(inner_alts) != 1:
            sys.exit("gen_prolog: nested Opt inside Opt is not supported")
        goals, args = inner_alts[0]
        if len(args) != 1:
            sys.exit("gen_prolog: opt(...) must carry exactly one Cap/Group")
        return [(goals, [f"some({args[0]})"]), ([], ["none"])]
    sys.exit(f"gen_prolog: unknown piece {part!r}")


# ---- print-side compiler: the INPUT is a concrete Term (destructured by the
# clause HEAD), the OUTPUT is Texts. Mirrors compile_parts_parse piece for
# piece; each piece contributes (subgoals, [(head_pattern_var_or_None, frag)]).

def compile_parts_print(parts, ctr, aux):
    alts = [([], [])]
    for part in parts:
        piece_alts = _piece_print(part, ctr, aux)
        alts = [(s0 + s1, f0 + f1) for s0, f0 in alts for s1, f1 in piece_alts]
    return alts


def _piece_print(part, ctr, aux):
    kind = type(part).__name__
    if kind == "KW":
        return [([], [(None, f"[{plq(part.text.lower())}]")])]
    if kind == "SYM":
        return [([], [(None, f"[{plq(part.text)}]")])]
    if kind == "Cap":
        v = ctr.next(part.field.capitalize() or "V")
        if part.kind == "ref":
            # the parse side's term argument here is rel(V), not bare V
            # (see _piece_parse) — the print HEAD PATTERN must destructure
            # the same wrapper to bind V, even though the printed FRAG is
            # just V's own text.
            return [([], [(f"rel({v})", f"[{v}]")])]
        if part.kind == "ident":
            return [([], [(v, f"[{v}]")])]
        if part.kind == "typename":
            return [([], [(v, f"[{v}]")])]
        if part.kind == "expr":
            t = ctr.next("T")
            return [([f"print_expr({v}, 0, {t})"], [(v, t)])]
        if part.kind.startswith("raw:"):
            tk = part.kind[4:]
            t = ctr.next("T")
            return [([f"raw_text({plq(tk)}, {v}, {t})"], [(v, t)])]
        sys.exit(f"gen_prolog: unknown Cap kind {part.kind!r}")
    if kind == "RuleRef":
        v, t = ctr.next(part.field.capitalize() or "V"), ctr.next("T")
        return [([f"print_rule_{part.name}({v}, {t})"], [(v, t)])]
    if kind == "Group":
        name = aux.group_print_name(part)
        v, t = ctr.next("G"), ctr.next("T")
        return [([f"{name}({v}, {t})"], [(v, t)])]
    if kind == "CommaList":
        name = aux.comma_list_print_name(part)
        v, t = ctr.next("L"), ctr.next("T")
        return [([f"{name}({v}, {t})"], [(v, t)])]
    if kind == "Choice":
        # every value this piece can hold is one of `options`' values (the
        # spec author picks `default` to coincide with one of them), so a
        # plain reverse lookup — no separate "absent" branch — always
        # resolves; canonical print always emits the explicit keyword.
        v, t = ctr.next("C"), ctr.next("T")
        chain = "fail"
        for src, val in part.options.items():
            chain = f"( {v}=={val} -> {t}=[{plq(src.lower())}] ; {chain} )"
        return [([chain], [(v, t)])]
    if kind == "Opt":
        return [_opt_print(part, ctr, aux)]
    sys.exit(f"gen_prolog: unknown piece {part!r}")


def _opt_print(part, ctr, aux):
    subgoals, frag_pairs = compile_parts_print(part.parts, ctr, aux)[0]
    kw_frags = [fr for pv, fr in frag_pairs if pv is None]
    value_pairs = [(pv, fr) for pv, fr in frag_pairs if pv is not None]
    if len(value_pairs) != 1:
        sys.exit("gen_prolog: opt(...) must carry exactly one Cap/Group")
    inner_var, inner_frag = value_pairs[0]
    v, t = ctr.next("O"), ctr.next("T")
    sub = (", ".join(subgoals) + ", ") if subgoals else ""
    # exp_42 fix (2026-09-05): keep SOURCE ORDER — the value may sit between
    # keywords, e.g. SAS `( in = a )`; the old kw_frags + [inner] put every
    # keyword first and printed `( in = ) a`.
    frags = ", ".join(fr for _pv, fr in frag_pairs)
    body = f"( {v}=some({inner_var}) -> {sub}flatten([{frags}], {t}) ; {t}=[] )"
    return ([body], [(v, t)])


class Aux:
    """Auxiliary DCG (parse) and predicate (print) clauses for every Group
    and CommaList piece — each gets one uniquely-named nonterminal, keyed
    by the Python object's id() so the parse pass (which creates it) and
    the later print pass (same Statement, same objects) share the name."""

    def __init__(self):
        self.ctr = Ctr()
        self.parse_lines = []
        self.print_lines = []
        self._group_names = {}
        self._cl_names = {}

    def emit_group(self, g, ctr):
        n = self.ctr.next("grp_")
        self._group_names[id(g)] = n
        for goals, args in compile_parts_parse(g.parts, ctr, self):
            term = f"{g.functor}({','.join(args)})" if args else g.functor
            body = ", ".join(goals) if goals else "[]"
            self.parse_lines.append(f"{n}({term}) --> {body}.")
        for subgoals, frag_pairs in compile_parts_print(g.parts, ctr, self):
            pattern_args = [pv for pv, _fr in frag_pairs if pv is not None]
            head_term = f"{g.functor}({','.join(pattern_args)})" if pattern_args else g.functor
            t_out = ctr.next("T")
            frags = [fr for _pv, fr in frag_pairs]
            goals = list(subgoals)
            goals.append(f"flatten([{', '.join(frags)}], {t_out})" if frags else f"{t_out}=[]")
            self.print_lines.append(f"{n}({head_term}, {t_out}) :- {', '.join(goals)}.")
        return n

    def emit_comma_list(self, cl, ctr):
        n = self.ctr.next("cl_")
        item = f"{n}_item"
        self._cl_names[id(cl)] = n
        for goals, args in compile_parts_parse(cl.parts, ctr, self):
            body = ", ".join(goals) if goals else "[]"
            term = args[0]  # one Cap/RuleRef/Group per comma_list item, by convention
            self.parse_lines.append(f"{item}({term}) --> {body}.")
        # `sep` (default a bare comma) between successive items — a list
        # of KW/SYM pieces, [] for CASE's WHEN..THEN's own juxtaposition
        # with no separator token at all (see pydsl_lib.sep_list).
        sep_goals = [match_kw_or_sym(p.text, ctr.next("K")) for p in cl.sep]
        rest_goals = sep_goals + [f"{item}(X)"]
        self.parse_lines += [
            f"{n}([X|Xs]) --> {item}(X), {n}_rest(Xs).",
            f"{n}_rest([X|Xs]) --> {', '.join(rest_goals)}, {n}_rest(Xs).",
            f"{n}_rest([]) --> [].",
        ]
        if cl.min == 0:
            self.parse_lines.append(f"{n}([]) --> [].")

        subgoals, frag_pairs = compile_parts_print(cl.parts, ctr, self)[0]
        item_pattern_args = [pv for pv, _fr in frag_pairs if pv is not None]
        if len(item_pattern_args) != 1:
            sys.exit("gen_prolog: a comma_list item must carry exactly one Cap/Group value")
        item_term = item_pattern_args[0]
        frags = [fr for _pv, fr in frag_pairs]
        t_out = ctr.next("T")
        goals = list(subgoals)
        goals.append(f"flatten([{', '.join(frags)}], {t_out})")
        self.print_lines.append(f"{item}({item_term}, {t_out}) :- {', '.join(goals)}.")
        sep_frags = [f"[{plq(p.text.lower() if is_word(p.text) else p.text)}]" for p in cl.sep]
        rest_frag_list = ", ".join(["TX"] + sep_frags + ["TXs"])
        self.print_lines += [
            f"{n}([X], Texts) :- !, {item}(X, Texts).",
            f"{n}([X|Xs], Texts) :- {item}(X, TX), {n}(Xs, TXs), flatten([{rest_frag_list}], Texts).",
        ]
        if cl.min == 0:
            self.print_lines.append(f"{n}([], []).")
        return n

    def group_print_name(self, g):
        return self._group_names[id(g)]

    def comma_list_print_name(self, cl):
        return self._cl_names[id(cl)]


def gen_statements(statements, stmt_end_sym, ctr, aux):
    """One Statement -> parse clauses (stmt_<name>//1 + stmt//1 dispatch)
    and print clauses (print_stmt_<name>/2 + print_stmt/2 dispatch).

    `stmt_end_sym` is None when the spec's own `statement_end` is `[]` —
    exp_014's XML lane (oozie.py) folds the WHOLE FILE as one statement
    (owner decision, 2026-08-24: an XML element tree has no per-statement
    terminator symbol the way a `;`-ended Pig/Hive statement does), so
    there is no trailing symbol to match on parse or emit on print. Every
    other language still passes its real symbol here unchanged."""
    lines, plines = [], []
    for st in statements:
        head = f"stmt_{st.name}"
        lhs_var = ctr.next("Lhs") if st.assign else None
        pre_parse = [f"[tok(word,{lhs_var})]", "[tok(symbol,'=')]"] if st.assign else []
        trailing_parse = [] if stmt_end_sym is None else [f"[tok(symbol,{plq(stmt_end_sym)})]"]
        # exp_42 (2026-09-05): a statement made of a raw block token (SAS
        # datalines) ends WITH that token — the tokeniser's eos_kinds already
        # closed the statement, so there is no trailing `;` to match or print.
        if any(type(pt).__name__ == "Cap" and pt.kind.startswith("raw:") for pt in st.parts):
            trailing_parse = []
            st_end_here = None
        else:
            st_end_here = stmt_end_sym

        for goals, args in compile_parts_parse(st.parts, ctr, aux):
            body = pre_parse + goals + trailing_parse
            inner = f"{st.name}({','.join(args)})" if args else st.name  # exp_42: `run`/`quit` carry no args
            term = f"assign(rel({lhs_var}), {inner})" if st.assign else inner
            lines.append(f"{head}({term}) --> {', '.join(body)}.")
        lines.append(f"stmt(T) --> {head}(T).")
        lines.append("")

        phead = f"print_stmt_{st.name}"
        for subgoals, frag_pairs in compile_parts_print(st.parts, ctr, aux):
            pattern_args = [pv for pv, _fr in frag_pairs if pv is not None]
            inner_pat = f"{st.name}({','.join(pattern_args)})" if pattern_args else st.name
            if st.assign:
                lhs_p = ctr.next("Lhs")
                term_pat = f"assign(rel({lhs_p}), {inner_pat})"
                lead = [f"[{lhs_p}]", "['=']"]
            else:
                term_pat, lead = inner_pat, []
            frags = lead + [fr for _pv, fr in frag_pairs]
            if st_end_here is not None:
                frags = frags + [f"[{plq(st_end_here)}]"]
            t_out = ctr.next("T")
            goals = list(subgoals)
            goals.append(f"flatten([{', '.join(frags)}], {t_out})")
            plines.append(f"{phead}({term_pat}, {t_out}) :- {', '.join(goals)}.")
        plines.append(f"print_stmt(T, Texts) :- {phead}(T, Texts), !.")
        plines.append("")
    return lines, plines


def gen_rules(rules, ctr, aux):
    """LANG.get("rules", {}) -> parse clauses (rule_<name>//1) and print
    clauses (print_rule_<name>/2), one predicate pair per {name: [RuleAlt,
    ...]} entry. Unlike a Statement, a rule consumes no leading "REF ="
    and no trailing statement-end symbol — it is a NAMED, embeddable
    sub-grammar, called from a Statement/Group/CommaList/expr-form via
    RuleRef (see pydsl_lib.rule_ref), including from within itself or
    another Rule that calls it back (recursion resolved by NAME, not by
    Python object identity — the mechanism behind Hive's `from_source`
    embedding `select_core` embedding `from_source` again for a FROM
    subquery). More than one RuleAlt under one name is an EITHER/OR,
    tried in Prolog-backtracking order — same discipline `forms` and
    `statements` already use for their own multi-shape dispatch."""
    lines, plines = [], []
    for name, alts in rules.items():
        head = f"rule_{name}"
        phead = f"print_rule_{name}"
        for ra in alts:
            for goals, args in compile_parts_parse(ra.parts, ctr, aux):
                body = ", ".join(goals) if goals else "[]"
                term = f"{ra.functor}({','.join(args)})" if args else ra.functor
                lines.append(f"{head}({term}) --> {body}.")
        lines.append("")
        for ra in alts:
            for subgoals, frag_pairs in compile_parts_print(ra.parts, ctr, aux):
                pattern_args = [pv for pv, _fr in frag_pairs if pv is not None]
                term_pat = f"{ra.functor}({','.join(pattern_args)})" if pattern_args else ra.functor
                frags = [fr for _pv, fr in frag_pairs]
                t_out = ctr.next("T")
                goals = list(subgoals)
                goals.append(f"flatten([{', '.join(frags)}], {t_out})" if frags else f"{t_out}=[]")
                plines.append(f"{phead}({term_pat}, {t_out}) :- {', '.join(goals)}.")
        plines.append("")
    return lines, plines


HEADER = """% GENERATED by pipeline/gen_prolog.py from pipeline/specs/{lang}.py — do not edit.
% stmt(Term, Tokens, []): DCG-callable parse direction (stmt//1, SWI-compiled to stmt/3).
% print_stmt(Term, Texts): canonical print direction (lowercase keywords, single spelling).
:- discontiguous stmt/3.
:- discontiguous print_stmt/2.
:- discontiguous prim/3.
:- discontiguous expr_own/3.

strip_quotes(V, S) :- sub_atom(V, 1, _, 1, S).

% ---- STRING-ESCAPE LAW (2026-08-26) -----------------------------------
% strip_quotes/2 above removes only the surrounding quote characters — it
% performs no un-escaping. Every quoted leaf's own tokeniser regex admits
% backslash-escape sequences (\\X for any X — see e.g. pig.py's string leaf
% doc, hive.py's, sqoop.py's, oozie.py's), so strip_quotes/2 was putting a
% raw, still-escaped backslash into the IR as if it were data: a Pig
% source value 'it\\'s' (4 real characters) survived fold+round-trip as
% the 5-character IR value it\\'s, with the backslash treated as a literal
% byte. unquote_escaped/3 and quote_escaped/3 below are the real
% (un)escaper every "string"/"atom" leaf now goes through instead. They
% are GENERIC — parameterised by DoubleDelim, a leaf-declared boolean
% (pipeline/pydsl/pydsl_lib.py Leaf.double_delim), never by a language name,
% per this file's own pyDSL-only law (see module docstring). The escape
% rule itself is universal across every spec's regex: \\X decodes to X for
% ANY X (dropping the backslash) — this is deliberately NOT full C-style
% escape decoding (\\t does not become an actual tab character; it decodes
% to the literal 2 characters "t" was already going to be, i.e. just drops
% the backslash). That narrower, unambiguously-correct rule is what fixes
% the demonstrated bug (an escaped delimiter or backslash surviving as
% extra data); full control-character escape semantics is a separate,
% NOT-attempted feature — see code_graph/gold/pig/coverage.md-adjacent
% notes, 2026-08-26 proposal, "what was deliberately not done".
%
% DoubleDelim=true also accepts a doubled delimiter character (e.g. Hive's
% '' / "") as an alternative one-character escape, matching the ONLY
% languages whose own tokeniser regex admits it.
unquote_escaped(DoubleDelim, RawText, Value) :-
    atom_codes(RawText, [Delim|Rest]),
    us_decode_body(DoubleDelim, Delim, Rest, Codes),
    atom_codes(Value, Codes).

us_decode_body(_, Delim, [Delim], []) :- !.
us_decode_body(true, Delim, [Delim, Delim|Rest], [Delim|Out]) :- !,
    us_decode_body(true, Delim, Rest, Out).
us_decode_body(DoubleDelim, Delim, [0'\\\\, C|Rest], [C|Out]) :- !,
    us_decode_body(DoubleDelim, Delim, Rest, Out).
us_decode_body(DoubleDelim, Delim, [C|Rest], [C|Out]) :-
    us_decode_body(DoubleDelim, Delim, Rest, Out).

% Encode direction (print): Delim is the CANONICAL print delimiter this
% leaf always uses (a fixed character code baked in per leaf at generate
% time — single-quote 0''' for every "string" leaf, double-quote 0'\" for
% Oozie's "atom" leaf — the same fixed choice LEAF_PRINT already made
% before this fix, e.g. printing a Hive value that arrived double-quoted
% back out with a single quote). Escapes exactly the two characters that
% would otherwise be structurally ambiguous in the output: the delimiter
% itself and a literal backslash. Nothing else needs escaping to be read
% back correctly.
quote_escaped(Delim, Value, Quoted) :-
    atom_codes(Value, Codes),
    us_encode_body(Delim, Codes, BodyCodes),
    flatten([[Delim], BodyCodes, [Delim]], AllCodes),
    atom_codes(Quoted, AllCodes).

us_encode_body(_, [], []).
us_encode_body(Delim, [C|Rest], [0'\\\\, C|Out]) :- ( C == Delim ; C == 0'\\\\ ), !,
    us_encode_body(Delim, Rest, Out).
us_encode_body(Delim, [C|Rest], [C|Out]) :-
    us_encode_body(Delim, Rest, Out).

% STRING-ROUND-TRIP-WARNING LAW (2026-08-26, owner decision: warn, not
% throw — a mismatch is reported to stderr and folding continues with the
% decoded Value as-is). Checks a VALUE round trip, not a text round trip:
% re-encode Value with this leaf's own canonical delimiter, then decode
% THAT back, and compare the two decoded values. Comparing against the
% original RawText directly would be wrong — canonicalisation legitimately
% changes the delimiter spelling (a Hive value that arrived double-quoted
% prints back single-quoted "on purpose), so text identity is not the
% right invariant here; value identity after a full round trip is. A
% mismatch means this token used an escape or delimiter shape
% unquote_escaped/quote_escaped cannot faithfully round-trip (e.g. a
% language-specific escape spelling beyond \\X / doubling — see the scope
% note above). This does not block the fold; it is a visibility law, not
% a correctness gate, per owner instruction.
warn_if_escape_not_reversible(DoubleDelim, Delim, Value, Context) :-
    ( quote_escaped(Delim, Value, Requoted),
      unquote_escaped(DoubleDelim, Requoted, Value2),
      Value2 == Value
    -> true
    ; format(user_error,
             'STRING-ESCAPE WARNING (~w): decoded value ~q does not survive a re-encode/re-decode round trip~n',
             [Context, Value])
    ).

"""


HEADER += """
% ---- exp_42 additions (2026-09-05) ------------------------------------
% unquote_plain/2, quote_plain/3: a quoted literal whose ONLY escape is the
% doubled delimiter (SAS: 'it''s' is it's; a backslash is a plain byte).
unquote_plain(RawText, Value) :-
    atom_codes(RawText, [Delim|Rest]),
    up_body(Delim, Rest, Codes),
    atom_codes(Value, Codes).
up_body(Delim, [Delim], []) :- !.
up_body(Delim, [Delim, Delim|Rest], [Delim|Out]) :- !, up_body(Delim, Rest, Out).
up_body(Delim, [C|Rest], [C|Out]) :- up_body(Delim, Rest, Out).
quote_plain(Delim, Value, Quoted) :-
    atom_codes(Value, Codes),
    qp_body(Delim, Codes, Body),
    flatten([[Delim], Body, [Delim]], All),
    atom_codes(Quoted, All).
qp_body(_, [], []).
qp_body(Delim, [Delim|Rest], [Delim, Delim|Out]) :- !, qp_body(Delim, Rest, Out).
qp_body(Delim, [C|Rest], [C|Out]) :- qp_body(Delim, Rest, Out).

% raw_body/2: a raw block token ("datalines; ...rows...") -> its trimmed body.
% raw_text/3: the print direction — head keyword, ';', newline, body, newline.
raw_body(Tok, Body) :-
    atom_codes(Tok, Codes),
    append(_, [0';|After], Codes), !,
    trim_ws(After, Trimmed),
    atom_codes(Body, Trimmed).
trim_ws(Cs, Out) :- drop_ws(Cs, C1), reverse(C1, R), drop_ws(R, R1), reverse(R1, Out).
drop_ws([C|Cs], Out) :- member(C, [0' , 0'\\t, 0'\\n, 0'\\r]), !, drop_ws(Cs, Out).
drop_ws(Cs, Cs).
raw_text(Kind, Body, [Text]) :-
    atomic_list_concat([Kind, ';\\n', Body, '\\n'], Text).
"""


def generate(lang):
    mod = importlib.import_module(f"pipeline.specs.{lang}")
    LANG = mod.LANG
    ladder, forms, expr_leaves = LANG["ladder"], LANG["forms"], LANG["expr_leaves"]
    statements = LANG["statements"]
    # An empty statement_end (oozie.py: the whole file is one statement,
    # so there is no per-statement terminator symbol) means stmt_end is
    # None end to end — see gen_statements' docstring for what that skips.
    stmt_end = LANG["statement_end"][0] if LANG["statement_end"] else None
    rules = LANG.get("rules", {})

    check_dequote_flag_is_meaningful(expr_leaves, lang)

    ctr, aux = Ctr(), Aux()
    ladder_lines, ladder_plines = gen_ladder(ladder, forms, expr_leaves, ctr, aux)
    rule_lines, rule_plines = gen_rules(rules, ctr, aux)
    stmt_lines, stmt_plines = gen_statements(statements, stmt_end, ctr, aux)

    out = [HEADER.format(lang=lang)]
    out.append("% ============================================================ statements")
    out += stmt_lines
    out.append("% ---- statement auxiliaries (comma_list / group sub-nonterminals) ----")
    out += aux.parse_lines
    out.append("")
    out.append("% ============================================================ named rules")
    out += rule_lines
    out.append("")
    out.append("% ============================================================ expression ladder")
    out += ladder_lines
    out.append("")
    out.append("% ============================================================ print direction")
    out += stmt_plines
    out.append("% ---- statement auxiliaries (print) ----")
    out += aux.print_lines
    out.append("")
    out.append("% ---- named rules (print) ----")
    out += rule_plines
    out.append("")
    out += ladder_plines

    out_dir = ROOT / "out" / "grammar"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{lang}.pl"
    out_path.write_text("\n".join(out) + "\n")
    print(f"wrote {out_path} ({len(out)} lines)")
    return out_path


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        sys.exit("usage: python3 -m pipeline.gen_prolog <lang>")
    for lang in argv:
        generate(lang)


if __name__ == "__main__":
    main()
