"""pipeline.codegen.hive_pyspark — Hive node/4 terms -> PySpark source.

Why this file exists: the ONLY place Hive term shapes are matched against
Python code strings. No cross-language branching lives here (the
Codegen law) — a Pig term is never recognised or rejected by name in
this file, it simply is not one of the functors this dispatcher knows,
and an unknown functor is a loud ValueError, never a silent no-op.

Dumb-printer contract: every function here takes an already-parsed term
(pipeline.term_parse tuples/atoms/numbers/lists) and returns PySpark
source text. Nothing in this file re-reads a .hql source file or an
io.json manifest — the term is the only input (Codegen law).

Term shapes handled (exactly the 6-file hive/small corpus, see
out/ir/hive/*.node4.json):
    create_external(rel(R), [field(N,T),...], lit(Sep), lit(Path), prop(lit(K),lit(V)))
    create_table_as(rel(R), select_stmt([select_core(...), ...], OrderByOpt, LimitOpt))
    create_table_cols(rel(R), [field(N,T),...])
    insert_select(rel(R), select_stmt([select_core(...), ...], OrderByOpt, LimitOpt))
select_core(ProjList, FromTable, JoinOpt, WhereOpt, GroupByOpt, HavingOpt)
    FromTable: table(rel(R), none|some(Alias)) | subquery(select_core(...), Alias)
    JoinOpt:   none | some(join(FromTable2, OnCond))
    WhereOpt / HavingOpt: none | some(Cond)
    GroupByOpt: none | some([col(F), ...])
OrderByOpt: none | some(orderby(KeyExpr, asc|desc))   (applies to the WHOLE
    select_stmt, i.e. after any UNION ALL of its select_core list — never
    to one core alone)
LimitOpt: none | some(lit(N))
proj: proj(Expr, none|some(Alias))
Expr shapes: col(F) | col(Rel,F) | lit(V) | star | cast(Expr,'TYPE') |
    gt/lt/ge/le/eq/ne | and/or/not | in(Expr,[lit,...]) |
    case_expr([when(Cond,ResultExpr),...], none|some(ElseExpr)) |
    call('COALESCE'|'COUNT'|'SUM'|'AVG'|'MIN'|'MAX', [Expr,...]) |
    subquery_expr(select_core(...))   (a scalar subquery)

FROM/JOIN aliasing rule: every base relation is already `.alias("<name>")`d
at CREATE EXTERNAL time; a `table(rel(R), some(Alias))` or a
`subquery(select_core(...), Alias)` re-aliases the resulting DataFrame to
that alias BEFORE any join, so qualified column refs (col(Rel,Field)) in
the join's ON condition and in a post-join WHERE always resolve — same
join pattern pig_pyspark.py already validated (side.alias(name), then a
boolean `on=` expression, never the `on="name"` string shorthand that
collapses same-named columns).

ORDER BY qualifier-stripping rule: ORDER BY/LIMIT apply to the *already
projected* select_stmt result, whose columns are Spark's own auto-derived
names — for an unaliased `F.col("o.order_id")` that is "order_id", never
"o.order_id" (Spark drops the qualifier). So an ORDER BY key that came in
qualified (col(Rel,Field)) is translated by dropping the qualifier
(_order_key_expr), never through the general expr_to_pyspark used inside
a select_core's own WHERE/JOIN/HAVING (where the qualifier is still live).

GROUP BY + HAVING rule: when a select_core has a GROUP BY, every distinct
aggregate call (repr-keyed) appearing in either its proj list or its
HAVING condition is computed exactly once inside `.agg(...)` under a
synthetic `_aggN` alias; translating the proj list / HAVING afterwards
redirects any matching aggregate call to `F.col("_aggN")` instead of
recomputing it against columns `.agg()` has already collapsed away — see
_iter_agg_calls / the `agg_map` threaded through expr_to_pyspark.

Scalar-subquery rule: `subquery_expr(select_core(...))` cannot become an
inline DataFrame expression (PySpark has no scalar-subquery operator), so
expr_to_pyspark recursively builds that inner select_core as its own
chain of statements (via the shared `ctx`), assigns a fresh
`_scalarN = <that chain>.collect()[0][0]`, and the surrounding expression
just references `_scalarN` — a real Python value computed at run time,
not at generation time.
"""
import json
from itertools import count
from pathlib import Path

from pipeline import term_parse
from pipeline.codegen import common

AGG_FUNCS = {"SUM": "sum", "COUNT": "count", "AVG": "avg", "MIN": "min", "MAX": "max"}
_BINOPS = {"add": "+", "sub": "-", "mul": "*", "div": "/"}
_CMPOPS = {"gt": ">", "lt": "<", "ge": ">=", "le": "<=", "eq": "==", "ne": "!="}


def _pyvar(name):
    """A Hive table/alias name, as a Python identifier. Every name in this
    corpus is already a valid identifier; this just makes that a
    guarantee instead of an assumption (mirrors pig_pyspark._pyvar, kept
    as a local duplicate rather than a cross-language import)."""
    out = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in name)
    if not out or out[0].isdigit():
        out = "_" + out
    return out


class _Ctx:
    """Accumulates the extra Python source lines a select_stmt's nested
    FROM-subqueries, JOINs, WHERE/GROUP BY/HAVING, and scalar subqueries
    need before the final `.select(...)` line — plus a single counter
    (shared across the whole generated program) handing out unique
    intermediate variable names, so no two statements' scratch variables
    ever collide even though the generated file has no per-statement
    function scope."""

    def __init__(self):
        self._n = count(1)
        self.lines = []

    def fresh(self, prefix):
        return f"_{prefix}{next(self._n)}"

    def emit(self, line):
        self.lines.append(line)

    def drain(self):
        out = self.lines
        self.lines = []
        return out


# --------------------------------------------------------------------
# small term helpers

def _proj_alias(proj):
    """proj(Expr, none|some(Alias)) -> (Expr, alias_str_or_None)."""
    _functor, expr, alias_term = proj
    alias = alias_term[1] if isinstance(alias_term, tuple) and alias_term[0] == "some" else None
    return expr, alias


def _lit_value(term):
    if isinstance(term, tuple) and term[0] == "lit":
        return term[1]
    raise ValueError(f"hive_pyspark: expected lit(...) in IN-list, got {term!r}")


def _some(opt):
    """opt is none|some(X): return X, or None if opt is 'none'."""
    if isinstance(opt, tuple) and opt[0] == "some":
        return opt[1]
    return None


def _iter_agg_calls(term):
    """Yield every call('SUM'|'COUNT'|'AVG'|'MIN'|'MAX', Args) subterm
    found anywhere inside `term` (a proj list, a single expr, whatever) —
    a generic structural walk, not tied to which functor is doing the
    containing. Used to find every aggregate a GROUP BY's proj list or
    HAVING condition needs computed inside `.agg(...)`."""
    if isinstance(term, tuple):
        functor, args = term[0], term[1:]
        if functor == "call" and args and args[0] in AGG_FUNCS:
            yield term
        for a in args:
            yield from _iter_agg_calls(a)
    elif isinstance(term, list):
        for item in term:
            yield from _iter_agg_calls(item)


def _has_header(prop_term):
    """prop(lit('skip.header.line.count'), lit('1')) -> True if that
    property is present with a positive count; False otherwise (no
    per-file case — this is a property-value read, same rule for every
    CREATE EXTERNAL TABLE statement)."""
    if not (isinstance(prop_term, tuple) and prop_term[0] == "prop"):
        return False
    key = prop_term[1][1] if isinstance(prop_term[1], tuple) else prop_term[1]
    val = prop_term[2][1] if isinstance(prop_term[2], tuple) else prop_term[2]
    if str(key) != "skip.header.line.count":
        return False
    try:
        return int(val) > 0
    except (TypeError, ValueError):
        return False


def _schema_code(fields):
    """fields: list of ('field', name, ir_type) tuples, ir_type an
    upper-case Hive type atom (e.g. 'DOUBLE'). Lowercases before handing
    to common.struct_field_code, which is the one shared type table."""
    parts = [common.struct_field_code(name, str(ir_type).lower()) for (_f, name, ir_type) in fields]
    return "StructType([" + ", ".join(parts) + "])"


# --------------------------------------------------------------------
# expressions

def expr_to_pyspark(term, ctx=None, agg_map=None):
    """term -> a PySpark source expression string.

    `ctx`, when given, lets a scalar subquery (subquery_expr) emit the
    extra statements it needs to compute its value before this expression
    can reference it.
    `agg_map`, when given (a select_core has a GROUP BY), redirects any
    aggregate call this expression contains to the `_aggN` column
    `.agg(...)` already computed it under, instead of recomputing it
    against columns that no longer exist post-aggregation.
    """
    if isinstance(term, bool):
        return f"F.lit({term!r})"
    if isinstance(term, (int, float)):
        return f"F.lit({term!r})"
    if term == "star":
        return "F.lit(1)"
    if isinstance(term, str):
        raise ValueError(f"expr_to_pyspark: unexpected bare atom {term!r}")

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

        if functor == "cast":
            inner, hive_type = args
            code = expr_to_pyspark(inner, ctx=ctx, agg_map=agg_map)
            return f'{code}.cast("{str(hive_type).lower()}")'

        if functor in _BINOPS:
            left = expr_to_pyspark(args[0], ctx=ctx, agg_map=agg_map)
            right = expr_to_pyspark(args[1], ctx=ctx, agg_map=agg_map)
            return f"({left} {_BINOPS[functor]} {right})"

        if functor in _CMPOPS:
            left = expr_to_pyspark(args[0], ctx=ctx, agg_map=agg_map)
            right = expr_to_pyspark(args[1], ctx=ctx, agg_map=agg_map)
            return f"({left} {_CMPOPS[functor]} {right})"

        if functor == "and":
            return f"({expr_to_pyspark(args[0], ctx=ctx, agg_map=agg_map)} & {expr_to_pyspark(args[1], ctx=ctx, agg_map=agg_map)})"
        if functor == "or":
            return f"({expr_to_pyspark(args[0], ctx=ctx, agg_map=agg_map)} | {expr_to_pyspark(args[1], ctx=ctx, agg_map=agg_map)})"
        if functor == "not":
            return f"(~{expr_to_pyspark(args[0], ctx=ctx, agg_map=agg_map)})"

        if functor == "in":
            target_expr, values = args
            target = expr_to_pyspark(target_expr, ctx=ctx, agg_map=agg_map)
            values_src = ", ".join(repr(_lit_value(v)) for v in values)
            return f"{target}.isin({values_src})"

        if functor == "case_expr":
            whens, else_opt = args
            code = None
            for when_term in whens:
                _wf, cond, result = when_term
                cond_code = expr_to_pyspark(cond, ctx=ctx, agg_map=agg_map)
                result_code = expr_to_pyspark(result, ctx=ctx, agg_map=agg_map)
                piece = f"F.when({cond_code}, {result_code})"
                code = piece if code is None else f"{code}.when({cond_code}, {result_code})"
            else_expr = _some(else_opt)
            else_code = expr_to_pyspark(else_expr, ctx=ctx, agg_map=agg_map) if else_expr is not None else "F.lit(None)"
            return f"{code}.otherwise({else_code})"

        if functor == "call":
            fname, fargs = args[0], args[1]
            if agg_map is not None and fname in AGG_FUNCS:
                key = repr(term)
                if key in agg_map:
                    return f'F.col("{agg_map[key]}")'
            if fname == "COALESCE":
                parts = ", ".join(expr_to_pyspark(a, ctx=ctx, agg_map=agg_map) for a in fargs)
                return f"F.coalesce({parts})"
            if fname in AGG_FUNCS:
                if len(fargs) != 1:
                    raise ValueError(f"expr_to_pyspark: {fname} expects 1 arg, got {fargs!r}")
                return f"F.{AGG_FUNCS[fname]}({expr_to_pyspark(fargs[0], ctx=ctx, agg_map=agg_map)})"
            raise ValueError(f"expr_to_pyspark: unmapped call target {fname!r} in {term!r}")

        if functor == "subquery_expr":
            if ctx is None:
                raise ValueError("expr_to_pyspark: subquery_expr encountered with no codegen context")
            (core_term,) = args
            inner_var = _select_core_to_var(core_term, ctx)
            scalar = ctx.fresh("scalar")
            ctx.emit(f"{scalar} = {inner_var}.collect()[0][0]")
            return scalar

        raise ValueError(f"expr_to_pyspark: unhandled functor {functor!r} in term {term!r}")

    raise ValueError(f"expr_to_pyspark: unexpected expression term {term!r}")


def _order_key_expr(term):
    """ORDER BY (and, by extension, LIMIT's ordering) apply to the select
    statement's already-projected result — a scope where Spark has
    already dropped any qualifier off an unaliased column (F.col("o.x")
    projects out as column "x", never "o.x"). A qualified col(Rel,Field)
    ORDER BY key is therefore translated to just the bare Field name."""
    if isinstance(term, tuple) and term[0] == "col":
        if len(term) == 2:
            return f'F.col("{term[1]}")'
        if len(term) == 3:
            return f'F.col("{term[2]}")'
    raise ValueError(f"hive_pyspark: unsupported ORDER BY key shape {term!r}")


# --------------------------------------------------------------------
# FROM / JOIN / GROUP BY / SELECT -> a chain of statements + a result var

def _from_table(term, ctx):
    """table(rel(R), none|some(Alias)) | subquery(select_core(...), Alias)
    -> the Python variable name holding that (aliased-if-needed) df."""
    if not isinstance(term, tuple):
        raise ValueError(f"hive_pyspark: unsupported FROM shape {term!r}")
    functor = term[0]

    if functor == "table":
        _functor, relref, alias_opt = term
        base_var = _pyvar(relref[1])
        alias = _some(alias_opt)
        if alias is None:
            return base_var
        var = ctx.fresh("t")
        ctx.emit(f'{var} = {base_var}.alias("{alias}")')
        return var

    if functor == "subquery":
        _functor, inner_core, alias = term
        inner_var = _select_core_to_var(inner_core, ctx)
        var = ctx.fresh("t")
        ctx.emit(f'{var} = {inner_var}.alias("{alias}")')
        return var

    raise ValueError(f"hive_pyspark: unsupported FROM shape {term!r}")


def _select_core_to_var(core_term, ctx):
    """select_core(ProjList, FromTable, JoinOpt, WhereOpt, GroupByOpt,
    HavingOpt) -> emits its chain of statements into `ctx` and returns
    the Python variable name of the final (projected) DataFrame."""
    _functor, proj_list, from_table, join_opt, where_opt, groupby_opt, having_opt = core_term

    cur_var = _from_table(from_table, ctx)

    join_term = _some(join_opt)
    if join_term is not None:
        _jf, right_from, on_cond = join_term
        right_var = _from_table(right_from, ctx)
        cond_code = expr_to_pyspark(on_cond, ctx=ctx)
        joined = ctx.fresh("j")
        ctx.emit(f'{joined} = {cur_var}.join({right_var}, on=({cond_code}), how="inner")')
        cur_var = joined

    where_cond = _some(where_opt)
    if where_cond is not None:
        cond_code = expr_to_pyspark(where_cond, ctx=ctx)
        filtered = ctx.fresh("w")
        ctx.emit(f"{filtered} = {cur_var}.filter({cond_code})")
        cur_var = filtered

    agg_map = None
    group_keys = _some(groupby_opt)
    having_cond = _some(having_opt)
    if group_keys is not None:
        key_codes = [expr_to_pyspark(k, ctx=ctx) for k in group_keys]

        agg_terms, seen = [], set()
        for t in _iter_agg_calls(proj_list):
            key = repr(t)
            if key not in seen:
                seen.add(key)
                agg_terms.append(t)
        if having_cond is not None:
            for t in _iter_agg_calls(having_cond):
                key = repr(t)
                if key not in seen:
                    seen.add(key)
                    agg_terms.append(t)

        agg_map = {}
        agg_parts = []
        for i, t in enumerate(agg_terms):
            alias = f"_agg{i}"
            agg_map[repr(t)] = alias
            agg_parts.append(f'{expr_to_pyspark(t, ctx=ctx)}.alias("{alias}")')

        grouped = ctx.fresh("g")
        keys_src = ", ".join(key_codes)
        aggs_src = ",\n    ".join(agg_parts)
        ctx.emit(f"{grouped} = {cur_var}.groupBy({keys_src}).agg(\n    {aggs_src}\n)")
        cur_var = grouped

    if having_cond is not None:
        having_code = expr_to_pyspark(having_cond, ctx=ctx, agg_map=agg_map)
        hv = ctx.fresh("h")
        ctx.emit(f"{hv} = {cur_var}.filter({having_code})")
        cur_var = hv

    proj_parts = []
    for proj in proj_list:
        expr, alias = _proj_alias(proj)
        code = expr_to_pyspark(expr, ctx=ctx, agg_map=agg_map)
        if alias:
            code = f'{code}.alias("{alias}")'
        proj_parts.append(code)
    sel = ctx.fresh("s")
    sel_src = ",\n    ".join(proj_parts)
    ctx.emit(f"{sel} = {cur_var}.select(\n    {sel_src}\n)")
    return sel


def _select_stmt_to_var(stmt_term, ctx):
    """select_stmt([select_core(...), ...], OrderByOpt, LimitOpt) -> the
    Python variable name of the final result, after unioning every
    select_core (UNION ALL semantics — PySpark's .union() keeps
    duplicates, matching Hive), then ORDER BY, then LIMIT."""
    _functor, cores, orderby_opt, limit_opt = stmt_term

    core_vars = [_select_core_to_var(c, ctx) for c in cores]
    cur = core_vars[0]
    for v in core_vars[1:]:
        nxt = ctx.fresh("u")
        ctx.emit(f"{nxt} = {cur}.union({v})")
        cur = nxt

    orderby_term = _some(orderby_opt)
    if orderby_term is not None:
        _of, key_expr, direction = orderby_term
        key_code = _order_key_expr(key_expr)
        if direction == "desc":
            key_code = f"{key_code}.desc()"
        elif direction == "asc":
            key_code = f"{key_code}.asc()"
        else:
            raise ValueError(f"hive_pyspark: unsupported ORDER BY direction {direction!r}")
        ordered = ctx.fresh("o")
        ctx.emit(f"{ordered} = {cur}.orderBy({key_code})")
        cur = ordered

    limit_term = _some(limit_opt)
    if limit_term is not None:
        n = limit_term[1]
        limited = ctx.fresh("l")
        ctx.emit(f"{limited} = {cur}.limit({n})")
        cur = limited

    return cur


# --------------------------------------------------------------------
# top-level statements -> one or more Python source lines

def _write_output_lines(var, relname, stem, lang):
    out_dir = common.pyspark_out_rel(lang, stem, relname)
    return [
        f'{var}.coalesce(1).write.mode("overwrite").option("sep", ",").csv("{out_dir.as_posix()}", header=False)',
    ]


def _emit_statement(term, stem, lang, ctx):
    functor = term[0] if isinstance(term, tuple) else term

    if functor == "create_external":
        _functor, relref, fields, sep_lit, path_lit, prop_term = term
        relname = relref[1]
        var = _pyvar(relname)
        sep = sep_lit[1]
        path = path_lit[1]
        header = _has_header(prop_term)
        schema = _schema_code(fields)
        return [
            f'{var} = spark.read.csv("{path}", schema={schema}, sep="{sep}", header={header})'
            f'.alias("{relname}")'
        ]

    if functor == "create_table_cols":
        _functor, relref, _fields = term
        relname = relref[1]
        return [
            f"# {relname}: schema declared here (create_table_cols) — "
            f"populated by a later INSERT INTO, nothing to compute yet"
        ]

    if functor in ("create_table_as", "insert_select"):
        _functor, relref, stmt_term = term
        relname = relref[1]
        var = _pyvar(relname)
        result_var = _select_stmt_to_var(stmt_term, ctx)
        lines = ctx.drain()
        lines.append(f"{var} = {result_var}")
        lines.extend(_write_output_lines(var, relname, stem, lang))
        return lines

    raise ValueError(f"hive_pyspark: unhandled top-level functor {functor!r} in term {term!r}")


# --------------------------------------------------------------------
# whole-program generation

def generate_lines(node4_entries, stem, lang="hive"):
    """node4_entries: the parsed *.node4.json list (each a dict with
    "block", "seq", "term", and — 2026-08-26 — "comments"). Returns the
    full generated program as a list of source lines (header, one
    "# blockid: b_00N" per distinct block followed by that block's
    statements, footer). See pig_pyspark.generate_lines' docstring (same
    shape) for the comment-placement rule."""
    lines = list(common.program_header(stem))
    ctx = _Ctx()
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
        stmt_lines = _emit_statement(term, stem, lang, ctx)
        if stmt_lines:
            stmt_lines[-1] = common.with_trailing(stmt_lines[-1], attachments, source_label)
        lines.extend(stmt_lines)

    lines.extend(common.program_footer())
    return lines


def generate_file(ir_json_path, out_py_path=None, lang="hive"):
    ir_json_path = Path(ir_json_path)
    node4_entries = json.loads(ir_json_path.read_text(encoding="utf-8"))
    stem = common.stem_of(ir_json_path)
    lines = generate_lines(node4_entries, stem, lang=lang)
    out_py_path = Path(out_py_path) if out_py_path else common.generated_script_path(lang, stem)
    common.write_program(out_py_path, lines)
    return out_py_path
