"""pipeline.codegen.pig_pyspark — Pig node/4 terms -> PySpark source.

Why this file exists: the ONLY place Pig term shapes are matched against
Python code strings. No cross-language branching lives here (the
Codegen law) — a Hive term is never recognised or rejected by name in
this file, it simply is not one of the functors this dispatcher knows,
and an unknown functor is a loud ValueError, never a silent no-op.

Dumb-printer contract: every function here takes an already-parsed term
(pipeline.term_parse tuples/atoms/numbers/lists) and returns PySpark
source text. Nothing in this file re-reads a .pig source file or an
io.json manifest — the term is the only input (Codegen law).

Term shapes handled (exactly the 6-file pig/small corpus, see
out/ir/pig/*.node4.json):
    assign(rel(R), load(lit(Path), call('PigStorage',[lit(Sep)]), [field(N,T),...]))
    assign(rel(R), filter(rel(S), BoolExpr))
    assign(rel(R), foreach(rel(S), [proj(Expr, none|some(Alias)), ...]))
    assign(rel(R), group(rel(S), col(Field)))
    assign(rel(R), join([side(rel(S1),Key1), side(rel(S2),Key2), ...]))
    assign(rel(R), order(rel(S), Key, asc|desc))
    assign(rel(R), limit(rel(S), lit(N)))
    assign(rel(R), distinct(rel(S)))
    assign(rel(R), union([rel(S1), rel(S2), ...]))
    store(rel(R), lit(Path), call('PigStorage',[lit(Sep)]))
    split(rel(S), [branch(rel(R1), Cond1), branch(rel(R2), Cond2), ...])
Expr shapes: col(F) | col(Rel,F) | lit(V) | paren(E) | add/sub/mul/div |
    gt/lt/ge/le/eq/ne | and/or/not | call('SUM'|'COUNT'|'AVG'|'MIN'|'MAX', [E])

Relation-qualification rule: every LOADed relation is `.alias("<name>")`d
at load time, so a later qualified reference col(Rel,Field) can always
resolve as F.col("Rel.Field") through filter/groupBy/join chains — this
is what lets JOIN's downstream FOREACH pick each side's columns apart
(the `raw_txn.txn_id` vs `customers.name` case in p04_join) without any
special-cased join-alias bookkeeping.

GROUP+FOREACH rule: a relation produced by `group(rel(S), col(Field))`
is remembered (name -> its physical group-key column name) purely so a
FOREACH over it is routed to `.agg(...)` instead of `.select(...)`; the
`group` pseudo-column inside its proj list is resolved from that
remembered physical name — see _foreach_grouped.
"""
import json
from pathlib import Path

from pipeline import term_parse
from pipeline.codegen import common

AGG_FUNCS = {"SUM": "sum", "COUNT": "count", "AVG": "avg", "MIN": "min", "MAX": "max"}
_BINOPS = {"add": "+", "sub": "-", "mul": "*", "div": "/"}
_CMPOPS = {"gt": ">", "lt": "<", "ge": ">=", "le": "<=", "eq": "==", "ne": "!="}


def _pyvar(name):
    """A Pig relation alias, as a Python identifier. Every alias in this
    corpus is already a valid identifier; this just makes that a
    guarantee instead of an assumption."""
    out = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in name)
    if not out or out[0].isdigit():
        out = "_" + out
    return out


def _proj_alias(proj):
    """proj(Expr, none|some(Alias)) -> (Expr, alias_str_or_None)."""
    _functor, expr, alias_term = proj
    alias = alias_term[1] if isinstance(alias_term, tuple) and alias_term[0] == "some" else None
    return expr, alias


def _qualify(key_expr, relname):
    """A JOIN/GROUP key expr may come in unqualified (col(Field)) or
    already qualified (col(Rel,Field)); always return the qualified
    3-tuple form so the generated F.col(...) is unambiguous."""
    if isinstance(key_expr, tuple) and key_expr[0] == "col":
        if len(key_expr) == 2:
            return ("col", relname, key_expr[1])
        if len(key_expr) == 3:
            return key_expr
    raise ValueError(f"pig_pyspark: unsupported join/group key shape {key_expr!r}")


# --------------------------------------------------------------------
# expressions

def expr_to_pyspark(term):
    if isinstance(term, (int, float)):
        return f"F.lit({term!r})"

    if isinstance(term, tuple):
        functor, args = term[0], term[1:]

        if functor == "col":
            if len(args) == 1:
                return f'F.col("{args[0]}")'
            if len(args) == 2:
                return f'F.col("{args[0]}.{args[1]}")'
            raise ValueError(f"expr_to_pyspark: unsupported col/{len(args)} in {term!r}")

        if functor == "lit":
            return f"F.lit({args[0]!r})"

        if functor == "paren":
            return f"({expr_to_pyspark(args[0])})"

        if functor in _BINOPS:
            return f"({expr_to_pyspark(args[0])} {_BINOPS[functor]} {expr_to_pyspark(args[1])})"

        if functor in _CMPOPS:
            return f"({expr_to_pyspark(args[0])} {_CMPOPS[functor]} {expr_to_pyspark(args[1])})"

        if functor == "and":
            return f"({expr_to_pyspark(args[0])} & {expr_to_pyspark(args[1])})"
        if functor == "or":
            return f"({expr_to_pyspark(args[0])} | {expr_to_pyspark(args[1])})"
        if functor == "not":
            return f"(~{expr_to_pyspark(args[0])})"
        if functor == "neg":
            return f"(-{expr_to_pyspark(args[0])})"

        if functor == "call":
            fname, fargs = args[0], args[1]
            if fname in AGG_FUNCS:
                if len(fargs) != 1:
                    raise ValueError(f"expr_to_pyspark: {fname} expects 1 arg, got {fargs!r}")
                return f"F.{AGG_FUNCS[fname]}({expr_to_pyspark(fargs[0])})"
            raise ValueError(f"expr_to_pyspark: unmapped call target {fname!r} in {term!r}")

        raise ValueError(f"expr_to_pyspark: unhandled functor {functor!r} in term {term!r}")

    raise ValueError(f"expr_to_pyspark: unexpected expression term {term!r}")


# --------------------------------------------------------------------
# statement RHS -> a single Python expression string

def _load_expr(term, relname):
    _functor, lit_path, storage_call, fields = term
    path = lit_path[1]
    sep = storage_call[2][0][1]
    schema = common.schema_code(fields)
    return (
        f'spark.read.csv("{path}", schema={schema}, sep="{sep}", header=False)'
        f'.alias("{relname}")'
    )


def _filter_expr(term):
    _functor, relref, cond = term
    return f"{_pyvar(relref[1])}.filter({expr_to_pyspark(cond)})"


def _group_expr(term, grouped_state, target_relname):
    _functor, relref, key_expr = term
    relname = relref[1]
    if not (isinstance(key_expr, tuple) and key_expr[0] == "col" and len(key_expr) == 2):
        raise ValueError(f"_group_expr: only a single unqualified col(Field) GROUP key is supported, got {key_expr!r}")
    key_field = key_expr[1]
    grouped_state[target_relname] = {"key_cols": [key_field]}
    return f"{_pyvar(relname)}.groupBy({expr_to_pyspark(key_expr)})"


def _foreach_plain(var, projs):
    cols = []
    for proj in projs:
        expr, alias = _proj_alias(proj)
        if expr == "group":
            raise ValueError("_foreach_plain: 'group' pseudo-column used on a non-grouped relation")
        code = expr_to_pyspark(expr)
        if alias:
            code = f'{code}.alias("{alias}")'
        cols.append(code)
    cols_block = ",\n    ".join(cols)
    return f"{var}.select(\n    {cols_block}\n)"


def _foreach_grouped(var, meta, projs):
    key_col = meta["key_cols"][0]
    agg_parts, select_parts = [], []
    for i, proj in enumerate(projs):
        expr, alias = _proj_alias(proj)
        if expr == "group":
            name = alias or key_col
            select_parts.append(f'F.col("{key_col}").alias("{name}")')
        else:
            name = alias or f"agg_{i}"
            agg_parts.append(f"{expr_to_pyspark(expr)}.alias(\"{name}\")")
            select_parts.append(f'F.col("{name}")')
    agg_block = ",\n    ".join(agg_parts)
    select_block = ",\n    ".join(select_parts)
    return f"{var}.agg(\n    {agg_block}\n).select(\n    {select_block}\n)"


def _foreach_expr(term, grouped_state):
    _functor, relref, projs = term
    relname = relref[1]
    var = _pyvar(relname)
    if relname in grouped_state:
        return _foreach_grouped(var, grouped_state[relname], projs)
    return _foreach_plain(var, projs)


def _join_expr(term):
    _functor, sides = term
    parsed = []
    for side in sides:
        _side_functor, relref, key_expr = side
        parsed.append((relref[1], key_expr))
    if len(parsed) < 2:
        raise ValueError(f"_join_expr: JOIN needs at least 2 sides, got {parsed!r}")

    name0, key0 = parsed[0]
    acc = f'{_pyvar(name0)}.alias("{name0}")'
    for name_i, key_i in parsed[1:]:
        left = expr_to_pyspark(_qualify(key0, name0))
        right = expr_to_pyspark(_qualify(key_i, name_i))
        cond = f"({left} == {right})"
        acc = f'{acc}.join({_pyvar(name_i)}.alias("{name_i}"), on={cond}, how="inner")'
    return acc


def _order_expr(term):
    _functor, relref, key_expr, direction = term
    code = expr_to_pyspark(key_expr)
    if direction == "desc":
        code = f"{code}.desc()"
    elif direction == "asc":
        code = f"{code}.asc()"
    else:
        raise ValueError(f"_order_expr: unsupported ORDER direction {direction!r}")
    return f"{_pyvar(relref[1])}.orderBy({code})"


def _limit_expr(term):
    _functor, relref, lit_n = term
    return f"{_pyvar(relref[1])}.limit({lit_n[1]})"


def _distinct_expr(term):
    _functor, relref = term
    return f"{_pyvar(relref[1])}.distinct()"


def _union_expr(term):
    _functor, rels = term
    names = [r[1] for r in rels]
    if not names:
        raise ValueError("_union_expr: UNION with no relations")
    acc = _pyvar(names[0])
    for n in names[1:]:
        acc = f"{acc}.union({_pyvar(n)})"
    return acc


_ASSIGN_RHS = {
    "load": _load_expr,
    "filter": lambda term, **_: _filter_expr(term),
    "order": lambda term, **_: _order_expr(term),
    "limit": lambda term, **_: _limit_expr(term),
    "distinct": lambda term, **_: _distinct_expr(term),
    "union": lambda term, **_: _union_expr(term),
}


# --------------------------------------------------------------------
# top-level statements -> one or more Python source lines

def _store_lines(term, stem, lang):
    _functor, relref, lit_path, storage_call = term
    relname = relref[1]
    path = lit_path[1]
    sep = storage_call[2][0][1]
    output_name = Path(path).name
    out_dir = common.pyspark_out_rel(lang, stem, output_name)
    var = _pyvar(relname)
    return [
        f'{var}.coalesce(1).write.mode("overwrite").option("sep", "{sep}").csv("{out_dir.as_posix()}", header=False)',
    ]


def _split_lines(term):
    _functor, src_relref, branches = term
    src_var = _pyvar(src_relref[1])
    lines = []
    for branch in branches:
        _branch_functor, branch_relref, cond = branch
        lines.append(f"{_pyvar(branch_relref[1])} = {src_var}.filter({expr_to_pyspark(cond)})")
    return lines


def _emit_statement(term, stem, grouped_state, lang):
    functor = term[0] if isinstance(term, tuple) else term

    if functor == "assign":
        _functor, relref, rhs = term
        relname = relref[1]
        var = _pyvar(relname)
        rhs_functor = rhs[0] if isinstance(rhs, tuple) else rhs

        if rhs_functor == "group":
            code = _group_expr(rhs, grouped_state, relname)
        elif rhs_functor == "foreach":
            code = _foreach_expr(rhs, grouped_state)
        elif rhs_functor == "join":
            code = _join_expr(rhs)
        elif rhs_functor in _ASSIGN_RHS:
            code = _ASSIGN_RHS[rhs_functor](rhs, relname=relname)
        else:
            raise ValueError(f"pig_pyspark: unhandled assign RHS functor {rhs_functor!r} in term {term!r}")
        return [f"{var} = {code}"]

    if functor == "store":
        return _store_lines(term, stem, lang)

    if functor == "split":
        return _split_lines(term)

    raise ValueError(f"pig_pyspark: unhandled top-level functor {functor!r} in term {term!r}")


# --------------------------------------------------------------------
# whole-program generation

def generate_lines(node4_entries, stem, lang="pig"):
    """node4_entries: the parsed *.node4.json list (each a dict with
    "block", "seq", "term", and — 2026-08-26 — "comments"). Returns the
    full generated program as a list of source lines (header, one
    "# blockid: b_00N" per distinct block followed by that block's
    statements, footer). Leading/prologue source comments get their own
    generated line right before the statement they belong to; trailing/
    inline ones (the fallback for a comment with no clean own-line spot)
    append to that statement's LAST generated line — see
    pipeline.comments' module docstring for the full attachment rule."""
    lines = list(common.program_header(stem))
    grouped_state = {}
    cur_block = None

    for entry in node4_entries:
        term = term_parse.parse_term(entry["term"])
        attachments = entry.get("comments", [])
        source_label = Path(entry["trace"]["file"]).name if entry.get("trace") else stem

        if entry["block"] != cur_block:
            if cur_block is not None:
                lines.append("")
            lines.append(common.blockid_header(entry["block"]))
            cur_block = entry["block"]

        lines.extend(common.comment_lines(attachments, source_label))
        stmt_lines = _emit_statement(term, stem, grouped_state, lang)
        if stmt_lines:
            stmt_lines[-1] = common.with_trailing(stmt_lines[-1], attachments, source_label)
        lines.extend(stmt_lines)

    lines.extend(common.program_footer())
    return lines


def generate_file(ir_json_path, out_py_path=None, lang="pig"):
    ir_json_path = Path(ir_json_path)
    node4_entries = json.loads(ir_json_path.read_text(encoding="utf-8"))
    stem = common.stem_of(ir_json_path)
    lines = generate_lines(node4_entries, stem, lang=lang)
    out_py_path = Path(out_py_path) if out_py_path else common.generated_script_path(lang, stem)
    common.write_program(out_py_path, lines)
    return out_py_path
