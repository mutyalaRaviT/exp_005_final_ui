"""pipeline.z3gen.gen — Z3 test-data ENGINE for the Pig medium corpus.

Why this file exists: corpus/pig/medium/p07_txn_region_tier.pig has three
FILTER conditions (one plain comparison, two compound AND/OR trees) that
Pig/PySpark must agree on for every row that could possibly reach them.
Rather than hand-type fixture rows and hope they cover every branch, this
engine walks the fold harness's own out/ir/pig/<stem>.node4.json — the
SAME node/4 terms codegen reads — finds every FILTER's condition tree,
and asks Z3 for a concrete row that makes each leg of it true, and
another that makes it false. The union of all those rows becomes the
corpus's input fixture (corpus/data/pig/medium_txn.csv +
medium_customers.csv).

Design, ported (not copied) from exp_009_executable_ast/spike/gen.py +
sas_semantics.py: "the table grows, the engine doesn't". Every functor's
MEANING lives in pipeline.z3gen.pig_semantics (CMP, BOOL); this file only
does the generic mechanics that never change when a new functor is
added: walk node/4 terms to learn each relation's PHYSICAL column
lineage (which LOADed table.field a relation's column really is, through
FILTER/JOIN/FOREACH passthrough and renaming), split a boolean condition
into (leaf, guards) legs the same way exp_009's edges.pl/gen.py did, and
solve one Z3 problem per leg x polarity.

Scope, deliberately smaller than exp_009's engine: Pig's FILTER operates
on a single row at a time (no groups, no aggregation branches — GROUP+
SUM/COUNT/AVG here are pure VALUE computations that never gate a
branch), and this corpus's only JOIN is a plain equi-join on a foreign
key. So there is no "K copies of a group" machinery and no SQL-select
compiler to port — just: lineage tracking, leaf/guard extraction, one
Z3 Solver call per (leg, polarity), and CSV writing.

Run:
    .venv/bin/python3 -m pipeline.z3gen.gen p07_txn_region_tier
        [--ir out/ir/pig/<stem>.node4.json]
        [--out-txn corpus/data/pig/medium_txn.csv]
        [--out-customers corpus/data/pig/medium_customers.csv]

Prints one line per (FILTER leg, polarity) scenario Z3 solved (or
couldn't), then a summary. Fix 5 (honesty restatement): the summary
reports N leaf conditions, each Z3-satisfiable in both polarities, with
every solved row ALSO constrained (Fix 1) to survive every FILTER
upstream of the one it targets — so the row is not just "possible", it
is a row that a real Pig/PySpark run would actually carry as far as the
targeted leg. That is NOT the same claim as "verified to reach and be
observed at a DataMatch output" — this script never runs Pig, PySpark,
or DataMatch itself; that end-to-end proof is
pipeline/tests/test_z3gen_medium_pig.py's job, re-running the real `pig
-x local` reference and `python3 -m pipeline.datamatch pig` separately.
Exits 0 iff every leaf condition found was Z3-satisfiable in both
polarities.
"""
import argparse
import csv
import json
import sys
from fractions import Fraction
from pathlib import Path

from z3 import Real, String, StringVal, RealVal, Solver, Not, sat

from pipeline import term_parse
from pipeline.z3gen.pig_semantics import CMP, BOOL, BOOL_LEAF_GUARD

REPO_ROOT = Path(__file__).resolve().parents[2]

# String columns get a small, readable candidate domain instead of being
# left to Z3's own unconstrained String model (which tends to hand back
# unreadable or empty values) — the same "tidy_constraints" spirit as
# exp_009's gen.py, just simpler because this corpus has no substring/
# concat functions to keep consistent with a length cap.
STRING_DOMAINS = {
    # Fix 3: alongside the canonical values, each domain carries one
    # case-variant ("east") and one whitespace-variant (" EAST") so Z3's
    # FALSE-polarity solves (the leg wanting `region == 'EAST'` to be
    # false, say) can land on a near-miss instead of always picking a
    # cleanly-different value like 'WEST'. A near-miss is what actually
    # distinguishes correct Pig `==` semantics (exact string equality)
    # from a buggy PySpark translation that quietly lowercases or trims
    # before comparing (mutations M4/M5) — DataMatch only catches those
    # if the fixture contains a row where they disagree. "EASTX" is a
    # THIRD kind of near-miss — same PREFIX as 'EAST' but a longer
    # string, so it distinguishes correct `==` from a buggy
    # `.startswith(...)` translation (mutation M7) the same way.
    # solve_scenario's _string_near_miss_candidates() is what actually
    # steers a FALSE-polarity solve onto one of these on purpose, rather
    # than leaving it to whichever domain member Z3 happens to pick.
    "region": ["EAST", "WEST", "NORTH", "SOUTH", "east", " EAST", "EASTX"],
    "channel": ["ONLINE", "STORE", "online", " ONLINE"],
    "tier": ["GOLD", "SILVER", "BRONZE", "gold", " GOLD"],
}

NUMERIC_TYPES = {"int", "integer", "long", "bigint", "double", "float"}


# ---------------------------------------------------------------------
# term helpers (pipeline.term_parse gives plain tuples: (functor, *args))

def functor(t):
    return t[0] if isinstance(t, tuple) else t


def targs(t):
    return t[1:] if isinstance(t, tuple) else ()


def show(t):
    """Pig-condition-looking text of a parsed term, for the report."""
    if isinstance(t, tuple):
        fn, a = t[0], t[1:]
        if fn == "col":
            return "::".join(str(x) for x in a)
        if fn == "lit":
            v = a[0]
            return repr(v) if isinstance(v, str) else str(v)
        if fn in CMP:
            sym = {"gt": ">", "ge": ">=", "lt": "<", "le": "<=", "eq": "==", "ne": "!="}[fn]
            return f"{show(a[0])} {sym} {show(a[1])}"
        if fn == "and":
            return f"({show(a[0])} AND {show(a[1])})"
        if fn == "or":
            return f"({show(a[0])} OR {show(a[1])})"
        if fn == "not":
            return f"NOT {show(a[0])}"
        if fn == "paren":
            return f"({show(a[0])})"
        return f"{fn}({', '.join(show(x) for x in a)})"
    return str(t)


# ---------------------------------------------------------------------
# Pass 1: walk node/4 terms, learn each relation's physical column lineage.

class Lineage:
    """schemas: table_name -> [(field, ir_type), ...], for every LOADed
    relation. rel_cols: relation_name -> {field_name: (table, field)} —
    where a relation's column PHYSICALLY comes from, so a FILTER three
    renames downstream of a LOAD can still be traced back to the LOADed
    table Z3 must generate rows for. join_pairs: [((t0,f0), (t1,f1)), ...]
    — every JOIN key equality found, so a scenario spanning two tables
    can assert the same match a real JOIN would require.
    filters: [{"target", "src", "cond", "seq"}, ...] in seq order."""

    def __init__(self):
        self.schemas = {}
        self.rel_cols = {}
        self.join_pairs = []
        self.filters = []
        # relation -> ("load",) | ("filter", src, cond) | ("join", [sides])
        # | ("foreach", src) | ("group", src): the generic "how was this
        # relation produced" map ancestor_filter_conds() walks upward
        # through (Fix 1 — see that method's docstring for why).
        self.producers = {}

    def resolve_col(self, col_term, default_rel):
        """col(Field) or col(Rel,Field) -> the (table, field) it physically
        is, by looking up the relation's own rel_cols map."""
        assert functor(col_term) == "col", f"resolve_col: not a col() term: {col_term!r}"
        a = targs(col_term)
        if len(a) == 1:
            rel, field = default_rel, a[0]
        elif len(a) == 2:
            rel, field = a
        else:
            raise ValueError(f"resolve_col: unsupported col/{len(a)} {col_term!r}")
        try:
            return self.rel_cols[rel][field]
        except KeyError as e:
            raise KeyError(f"resolve_col: relation {rel!r} has no known column {field!r} "
                            f"(known relations: {sorted(self.rel_cols)})") from e

    def walk(self, node4_entries):
        for entry in node4_entries:
            term = term_parse.parse_term(entry["term"])
            fn = functor(term)
            if fn == "assign":
                relref, rhs = targs(term)
                target = targs(relref)[0]
                self._walk_assign(target, rhs, entry["seq"])
            # store/split/order/limit/distinct/union: no new column lineage
            # (their input relation's rel_cols already covers everything
            # downstream code could reference) — nothing to learn here.

    def _walk_assign(self, target, rhs, seq):
        rfn = functor(rhs)
        if rfn == "load":
            lit_path, _storage, fields = targs(rhs)
            field_list = [(f_name, f_type) for (_ff, f_name, f_type) in fields]
            self.schemas[target] = field_list
            self.rel_cols[target] = {name: (target, name) for name, _t in field_list}
            self.producers[target] = ("load",)
        elif rfn == "filter":
            relref_src, cond = targs(rhs)
            src = targs(relref_src)[0]
            self.rel_cols[target] = self.rel_cols[src]  # passthrough: same physical columns
            self.filters.append({"target": target, "src": src, "cond": cond, "seq": seq})
            self.producers[target] = ("filter", src, cond)
        elif rfn == "join":
            (sides,) = targs(rhs)
            parsed = []
            for side in sides:
                _sf, relref_i, key_i = side
                parsed.append((targs(relref_i)[0], key_i))
            name0, key0 = parsed[0]
            phys0 = self.resolve_col(key0, name0)
            for name_i, key_i in parsed[1:]:
                physi = self.resolve_col(key_i, name_i)
                self.join_pairs.append((phys0, physi))
            # The join's OUTPUT relation is never addressed by name downstream
            # in this corpus — every FOREACH after a JOIN qualifies columns
            # by the original SIDE name (see p04_join.pig / p07's IR), so
            # target gets no rel_cols entry of its own. It still gets a
            # producers entry (its two SIDE names), so ancestor_filter_conds
            # can walk through it to find filters upstream of BOTH sides.
            self.producers[target] = ("join", [name_i for name_i, _k in parsed])
        elif rfn == "foreach":
            relref_src, projs = targs(rhs)
            src = targs(relref_src)[0]
            new_cols = {}
            for proj in projs:
                _pf, expr, alias_term = proj
                if expr == "group":
                    continue  # GROUP's pseudo-column: aggregation-context only, not a branch input
                if isinstance(expr, tuple) and functor(expr) == "call":
                    continue  # an aggregate VALUE (SUM/COUNT/AVG), never a branch input
                if not (isinstance(expr, tuple) and functor(expr) == "col"):
                    continue  # nothing else appears in this corpus's projections
                alias = targs(alias_term)[0] if (isinstance(alias_term, tuple) and functor(alias_term) == "some") else None
                name = alias or targs(expr)[-1]
                new_cols[name] = self.resolve_col(expr, src)
            self.rel_cols[target] = new_cols
            self.producers[target] = ("foreach", src)
        elif rfn == "group":
            # this corpus always aggregates back over the ORIGINAL loaded
            # relation (see p03_group_agg.pig / p07's `raw_txn.amount`),
            # never through the GROUP's own output name, so rel_cols has
            # nothing to learn here — but the producer edge is still
            # recorded (a future script's FILTER on a grouped relation
            # would need it for ancestor_filter_conds).
            relref_src, _key = targs(rhs)
            src = targs(relref_src)[0]
            self.producers[target] = ("group", src)
        # order/limit/distinct/union: not used by any FILTER-bearing lineage
        # in this corpus; add a branch here the day a script needs one.

    def ancestor_filter_conds(self, rel):
        """Fix 1: walk producers upward from `rel`, collecting every
        ancestor FILTER's (cond, src) this scenario's row must ALSO
        satisfy (polarity True — a FILTER only lets a row through when
        its condition holds) to have physically reached `rel` at all.
        Without this, solve_scenario only knows about the ONE FILTER
        whose leg it is solving — so a row built to satisfy FILTER 3's
        gold-tier leg, say, can come back amount=-5, which never even
        survives FILTER 1, and the "gold_txn true-leg witness" never
        shows up in the real output.

        A JOIN has two (or more) sides; a row that reached a relation
        downstream of a JOIN passed through EVERY side's own filter
        chain, so all sides are walked. `seen` guards against revisiting
        a relation reachable by more than one path (not needed by this
        corpus's single JOIN, but cheap insurance against an infinite
        walk if a future script's lineage ever cycles back)."""
        out = []
        seen = set()

        def walk(r):
            if r in seen:
                return
            seen.add(r)
            prod = self.producers.get(r)
            if prod is None:
                return
            kind = prod[0]
            if kind == "filter":
                _, src, cond = prod
                out.append((cond, src))
                walk(src)
            elif kind == "foreach":
                _, src = prod
                walk(src)
            elif kind == "group":
                _, src = prod
                walk(src)
            elif kind == "join":
                _, sides = prod
                for side in sides:
                    walk(side)
            # "load": nothing further upstream — stop.

        walk(rel)
        return out


# ---------------------------------------------------------------------
# Pass 2: split a FILTER's boolean tree into (leaf, guards) legs.

def leaves(cond, guards):
    """Yield (leaf_comparison_term, guards) pairs. `guards` is a list of
    (guard_condition_term, required_bool) that must hold before this leg
    is reached — exactly exp_009's edges.pl/gen.py `leaves()` rule: AND's
    right leg is only reached once its left is true; OR's right leg only
    once its left is false. `not` and `paren` are transparent wrappers."""
    fn = functor(cond)
    if fn == "paren":
        yield from leaves(targs(cond)[0], guards)
    elif fn in BOOL_LEAF_GUARD:  # "and" / "or"
        left, right = targs(cond)
        yield from leaves(left, guards)
        yield from leaves(right, guards + [(left, BOOL_LEAF_GUARD[fn])])
    elif fn == "not":
        yield from leaves(targs(cond)[0], guards)
    else:
        yield cond, guards  # a comparison: gt/ge/lt/le/eq/ne


def collect_phys(cond, src, lineage):
    """Every (table, field) a condition subtree reads, via lineage.resolve_col."""
    fn = functor(cond)
    if fn == "col":
        return {lineage.resolve_col(cond, src)}
    out = set()
    for a in targs(cond):
        if isinstance(a, tuple):
            out |= collect_phys(a, src, lineage)
    return out


def expand_via_joins(tables_needed, join_pairs):
    """If a scenario touches one side of a known JOIN key equality, pull in
    the other side too — a customer_tier-only scenario still needs a
    matching raw_txn row, or there is nothing for it to actually join
    with in the real pipeline."""
    tables_needed = set(tables_needed)
    changed = True
    while changed:
        changed = False
        for (t0, _f0), (t1, _f1) in join_pairs:
            if t0 in tables_needed and t1 not in tables_needed:
                tables_needed.add(t1)
                changed = True
            if t1 in tables_needed and t0 not in tables_needed:
                tables_needed.add(t0)
                changed = True
    return tables_needed


# ---------------------------------------------------------------------
# Pass 3: build + solve one Z3 problem per (leg, polarity).

def normalize(cond, src, lineage):
    """Rewrite every col(...) in `cond` to a canonical ('phys', table,
    field) node, so build_expr never needs relation context again."""
    fn = functor(cond)
    if fn == "col":
        table, field = lineage.resolve_col(cond, src)
        return ("phys", table, field)
    if fn == "lit":
        return cond
    return (fn,) + tuple(normalize(a, src, lineage) for a in targs(cond))


def lit_z3(value):
    return StringVal(value) if isinstance(value, str) else RealVal(value)


def build_operand(node, var_of):
    if functor(node) == "phys":
        _f, table, field = node
        return var_of(table, field)
    if functor(node) == "lit":
        return lit_z3(targs(node)[0])
    raise ValueError(f"build_operand: unsupported operand {node!r}")


def build_expr(node, var_of):
    fn = functor(node)
    if fn == "paren":
        return build_expr(targs(node)[0], var_of)
    if fn in CMP:
        x, y = targs(node)
        return CMP[fn](build_operand(x, var_of), build_operand(y, var_of))
    if fn == "not":
        return BOOL["not"](build_expr(targs(node)[0], var_of))
    if fn in BOOL:
        x, y = targs(node)
        return BOOL[fn](build_expr(x, var_of), build_expr(y, var_of))
    raise ValueError(f"build_expr: unhandled functor {fn!r} in {node!r}")


def z3_kind(ir_type):
    return "num" if ir_type in NUMERIC_TYPES else "str"


def make_row_vars(table, schema, scenario_id):
    cols = {}
    for name, ir_type in schema:
        varname = f"{table}.{name}#{scenario_id}"
        cols[name] = Real(varname) if z3_kind(ir_type) == "num" else String(varname)
    return cols


def apply_domain_and_bounds(solver, tables_needed, schemas, row_vars):
    for table in tables_needed:
        for name, ir_type in schemas[table]:
            var = row_vars[table][name]
            if z3_kind(ir_type) == "num":
                solver.add(var >= -50, var <= 2000)
            elif name in STRING_DOMAINS:
                domain = STRING_DOMAINS[name]
                solver.add(_or_eq(var, domain))
            # 'name' (customer name) has no domain: it is not branch-
            # relevant and is overwritten post-hoc, see fill_extra_columns.


def _or_eq(var, domain):
    from z3 import Or
    return Or([var == StringVal(v) for v in domain])


def _boundary_pin(normalized_leaf, var_of):
    """Fix 3 (numeric half): if `normalized_leaf` is a strict/non-strict
    numeric comparison against a literal threshold (`amount > 100.0`,
    etc.), return [(var, literal)] — a single-candidate preference group
    — so the caller can TRY pinning the row's value exactly onto that
    threshold before falling back to a plain solve. A `gt`/`lt` leaf is
    False exactly ON its own boundary and a `ge`/`le` leaf is True
    exactly on its own boundary, so whichever polarity is being solved,
    pinning to the boundary is either consistent (and gives the
    sharpest possible witness — the row that would flip PASS to FAIL
    under a `>`<->`>=` mutation like M1/M2) or inconsistent (and the
    caller's push/pop just discards the hint and solves normally, so
    this is always safe to attempt). Returns None if `normalized_leaf`
    isn't shaped this way."""
    fn = functor(normalized_leaf)
    if fn not in ("gt", "ge", "lt", "le"):
        return None
    x, y = targs(normalized_leaf)
    if functor(x) == "phys" and functor(y) == "lit" and not isinstance(targs(y)[0], str):
        return [(build_operand(x, var_of), lit_z3(targs(y)[0]))]
    if functor(y) == "phys" and functor(x) == "lit" and not isinstance(targs(x)[0], str):
        return [(build_operand(y, var_of), lit_z3(targs(x)[0]))]
    return None


def _string_near_miss_candidates(normalized_leaf, polarity, var_of):
    """Fix 3 (string half): if `normalized_leaf` is a string `eq`/`ne`
    against a literal, AND the polarity being solved means "this must
    come out NOT EQUAL" (eq+False, or ne+True), return a preference
    group of near-miss variants of that same literal to try pinning the
    row to, before falling back to whatever Z3 finds on its own (which,
    left unconstrained beyond STRING_DOMAINS' Or-of-equalities, could
    just as easily land on a totally unrelated value like 'WEST' — real,
    but useless for exposing a translation bug in THIS comparison).
    Three near-miss shapes, each targeting one specific mistranslation:
      - lowercase(literal)      -> catches a buggy .lower() (M4)
      - " " + literal           -> catches a buggy .strip()/.trim() (M5)
      - literal + "X"           -> same PREFIX, different string, so it
                                    catches a buggy .startswith(...) (M7)
    Every candidate returned here must also be a member of that column's
    STRING_DOMAINS entry (see gen.py's STRING_DOMAINS table) — this
    function only PREFERS among values Z3 was already allowed to pick;
    it does not loosen what Z3 may return. If the constrained candidate
    isn't satisfiable (e.g. it collides with a `guards` requirement),
    the caller's push/pop discards it and tries the next one, or falls
    back to a plain solve — so this is always safe to attempt."""
    fn = functor(normalized_leaf)
    if fn not in ("eq", "ne"):
        return None
    intends_not_equal = (fn == "eq" and not polarity) or (fn == "ne" and polarity)
    if not intends_not_equal:
        return None
    x, y = targs(normalized_leaf)
    if functor(x) == "phys" and functor(y) == "lit" and isinstance(targs(y)[0], str):
        var, literal = build_operand(x, var_of), targs(y)[0]
    elif functor(y) == "phys" and functor(x) == "lit" and isinstance(targs(x)[0], str):
        var, literal = build_operand(y, var_of), targs(x)[0]
    else:
        return None
    candidates = []
    if literal.lower() != literal:
        candidates.append(literal.lower())
    if not literal.startswith(" "):
        candidates.append(" " + literal)
    candidates.append(literal + "X")
    return [(var, lit_z3(c)) for c in candidates]


def num_of(z3_val, ir_type):
    s = str(z3_val)
    fr = Fraction(s)
    f = float(fr)
    if ir_type in ("int", "integer", "long", "bigint"):
        return int(round(f))
    return round(f, 2)


def solve_scenario(lineage, src, leaf, guards, polarity, scenario_id, ancestor_conds=()):
    phys = collect_phys(leaf, src, lineage)
    for g_term, _want in guards:
        phys |= collect_phys(g_term, src, lineage)
    for a_cond, a_src in ancestor_conds:
        phys |= collect_phys(a_cond, a_src, lineage)
    tables_needed = {t for t, _f in phys}
    tables_needed = expand_via_joins(tables_needed, lineage.join_pairs)

    solver = Solver()
    row_vars = {t: make_row_vars(t, lineage.schemas[t], scenario_id) for t in tables_needed}

    def var_of(table, field):
        return row_vars[table][field]

    for (t0, f0), (t1, f1) in lineage.join_pairs:
        if t0 in tables_needed and t1 in tables_needed:
            solver.add(row_vars[t0][f0] == row_vars[t1][f1])

    apply_domain_and_bounds(solver, tables_needed, lineage.schemas, row_vars)

    # Fix 1: a row solved for THIS filter's leg must also satisfy every
    # FILTER standing between `src` and the original LOADed relation(s) —
    # otherwise Z3 is free to hand back a row that dies at an earlier
    # FILTER before ever reaching the leg it was built to test. Every
    # ancestor condition is asserted True (a FILTER only lets a row
    # through when its condition holds), normalized in ITS OWN src's
    # column context (not this leg's `src`) since that is the relation
    # its col() references were originally written against.
    for a_cond, a_src in ancestor_conds:
        a_expr = build_expr(normalize(a_cond, a_src, lineage), var_of)
        solver.add(a_expr)

    for g_term, want in guards:
        g_expr = build_expr(normalize(g_term, src, lineage), var_of)
        solver.add(g_expr if want else Not(g_expr))

    normalized_leaf = normalize(leaf, src, lineage)
    leaf_expr = build_expr(normalized_leaf, var_of)
    solver.add(leaf_expr if polarity else Not(leaf_expr))

    # Fix 3: try landing on a SHARP witness first — either exactly on the
    # leaf's own numeric threshold (_boundary_pin) or on a near-miss
    # variant of its string literal (_string_near_miss_candidates) — in
    # that preference order, each candidate tried via its own push()/
    # pop() and discarded if it conflicts with anything already asserted
    # (ancestor conditions, guards, the leaf's own polarity). The FIRST
    # candidate that is still satisfiable wins; if none are, this falls
    # back to a plain solve exactly as before Fix 3 — so none of this
    # can ever turn a previously-sat scenario into an unsat one.
    preference_groups = []
    b_pins = _boundary_pin(normalized_leaf, var_of)
    if b_pins:
        preference_groups.append(b_pins)
    s_pins = _string_near_miss_candidates(normalized_leaf, polarity, var_of)
    if s_pins:
        preference_groups.append(s_pins)

    pinned = False
    for group in preference_groups:
        if pinned:
            break
        for var, literal in group:
            solver.push()
            solver.add(var == literal)
            if solver.check() == sat:
                pinned = True
                break
            solver.pop()

    if not pinned and solver.check() != sat:
        return None
    model = solver.model()

    # Fix 4: Z3's model is exact rationals; num_of() below rounds them to
    # what the CSV fixture can actually hold (2dp floats, or ints). Round
    # first, THEN re-check the rounded values against every constraint
    # this scenario asserted (guards, the leaf itself, and now the
    # ancestor conditions) — a tight-enough interval can solve to an
    # exact rational that rounds to a value JUST outside it (e.g.
    # `amount > 100.0 and amount < 100.001` rounds to 100.0, which fails
    # `> 100.0` even though Z3 reported sat). If the rounded row no
    # longer satisfies everything it was solved for, this is a soundness
    # bug in the making — raise loudly instead of silently writing a
    # wrong row.
    rows = {}
    for table in tables_needed:
        row = {}
        for name, ir_type in lineage.schemas[table]:
            v = model.eval(row_vars[table][name], model_completion=True)
            row[name] = v.as_string() if z3_kind(ir_type) == "str" else num_of(v, ir_type)
        rows[table] = row

    _recheck_rounded_row(lineage, src, leaf, guards, polarity, ancestor_conds, rows, tables_needed)

    return rows


def _recheck_rounded_row(lineage, src, leaf, guards, polarity, ancestor_conds, rows, tables_needed):
    """Fix 4's re-check: evaluate every asserted condition in plain Python
    against the ROUNDED row values (not Z3's exact rationals) and assert
    each one still comes out the way it was solved for. This is the
    "after rounding, re-check" half of Fix 4 — see solve_scenario's
    comment for the failure mode this guards against."""

    def col_value(table, field):
        return rows[table][field]

    def pyeval(node, node_src):
        fn = functor(node)
        if fn == "phys":
            _f, table, field = node
            return col_value(table, field)
        if fn == "lit":
            return targs(node)[0]
        if fn == "col":
            table, field = lineage.resolve_col(node, node_src)
            return col_value(table, field)
        raise ValueError(f"_recheck_rounded_row: unsupported operand {node!r}")

    def pybool(node, node_src):
        fn = functor(node)
        if fn == "paren":
            return pybool(targs(node)[0], node_src)
        if fn in CMP:
            x, y = targs(node)
            xv, yv = pyeval(x, node_src), pyeval(y, node_src)
            return {
                "gt": lambda a, b: a > b, "ge": lambda a, b: a >= b,
                "lt": lambda a, b: a < b, "le": lambda a, b: a <= b,
                "eq": lambda a, b: a == b, "ne": lambda a, b: a != b,
            }[fn](xv, yv)
        if fn == "not":
            return not pybool(targs(node)[0], node_src)
        if fn == "and":
            x, y = targs(node)
            return pybool(x, node_src) and pybool(y, node_src)
        if fn == "or":
            x, y = targs(node)
            return pybool(x, node_src) or pybool(y, node_src)
        raise ValueError(f"_recheck_rounded_row: unhandled functor {fn!r} in {node!r}")

    problems = []
    for a_cond, a_src in ancestor_conds:
        if not pybool(a_cond, a_src):
            problems.append(f"ancestor condition {show(a_cond)!r} (src={a_src}) no longer holds")
    for g_term, want in guards:
        if pybool(g_term, src) != want:
            problems.append(f"guard {show(g_term)!r} (src={src}) wanted {want}, rounded row gives {not want}")
    leaf_ok = pybool(leaf, src)
    if leaf_ok != polarity:
        problems.append(f"leaf {show(leaf)!r} (src={src}) wanted polarity={polarity}, rounded row gives {leaf_ok}")

    if problems:
        raise AssertionError(
            "Fix 4 re-check failed: Z3 reported sat but the ROUNDED row breaks "
            f"{len(problems)} condition(s) it was solved for: {problems}. "
            f"rows={ {t: rows[t] for t in tables_needed} }"
        )


# ---------------------------------------------------------------------
# Pass 4: run every FILTER's every leg x polarity, collect rows, report.

def run(node4_entries):
    lineage = Lineage()
    lineage.walk(node4_entries)

    raw_rows = []       # list of dicts, one per solved raw_txn row
    cust_by_id = {}      # customer_id -> dict, deduped
    scenarios = []       # report rows
    scenario_id = 0

    for f in lineage.filters:
        # Fix 1: every ancestor FILTER standing between f["src"] and the
        # original LOADed relation(s) — computed once per filter, reused
        # across all of its legs x polarities.
        ancestor_conds = lineage.ancestor_filter_conds(f["src"])
        for leaf, guards in leaves(f["cond"], []):
            for polarity in (True, False):
                scenario_id += 1
                rows = solve_scenario(lineage, f["src"], leaf, guards, polarity, scenario_id,
                                       ancestor_conds)
                sat_ok = rows is not None
                scenarios.append({
                    "filter": f["target"], "leaf": show(leaf),
                    "guards": [(show(g), w) for g, w in guards],
                    "polarity": polarity, "sat": sat_ok,
                })
                if not sat_ok:
                    continue
                offset = scenario_id * 100  # keep ids distinct across scenarios
                if "raw_txn" in rows:
                    r = dict(rows["raw_txn"])
                    r["customer_id"] += offset
                    raw_rows.append(r)
                    linked_cust_id = r["customer_id"]
                else:
                    linked_cust_id = None
                if "customers" in rows:
                    c = dict(rows["customers"])
                    c["customer_id"] += offset
                    cust_by_id[c["customer_id"]] = c
                elif linked_cust_id is not None:
                    # raw_txn-only scenario (no customers side needed): still
                    # give it a customer master row so it CAN join if it
                    # happens to reach that far, matching a real Pig fixture.
                    cust_by_id[linked_cust_id] = {
                        "customer_id": linked_cust_id, "name": f"Cust_{linked_cust_id}",
                        "tier": "SILVER",
                    }

    return lineage, scenarios, raw_rows, cust_by_id


# A couple of hand-added rows (not Z3-derived — the brief's own carve-out)
# purely for join/group MULTIPLICITY: more than one row per region so
# SUM/COUNT/AVG in region_summary are not trivially single-row, and more
# than one customer per tier so the JOIN has real fan-out. Every value
# here is unconstrained by any branch — they exist for volume, not coverage.
#
# The LAST five rows are a different kind of hand-added witness (Fix 3):
# Z3's own boundary-pin / near-miss preferences (solve_scenario, above)
# only control the ONE column the leaf/guard being solved actually
# constrains — every OTHER column on that same row (region, channel) is
# still Z3's free arbitrary pick from STRING_DOMAINS, so a row built to
# sit exactly on FILTER 1's `amount > 0.0` boundary can just as easily
# come back with channel="online" (lowercase) or region="EASTX" — values
# that ALSO happen to exclude it from qualifying_txn for unrelated
# reasons, silently hiding the very boundary/near-miss it was built to
# expose. These two rows pin EVERY relevant column by hand so the
# witness is guaranteed observable no matter what Z3 picked elsewhere:
#   - amount==0.0, channel=ONLINE: the exact `amount > 0.0` boundary,
#     reaching qualifying_txn via the channel=='ONLINE' branch alone (so
#     the amount value at the boundary is what's on trial, not region).
#     Catches M1 (`>` -> `>=` on FILTER 1).
#   - amount=150.0 (>100, <200), region="EASTX", channel=STORE: real Pig
#     excludes it (EASTX != EAST, channel != ONLINE); a `.startswith('EA')`
#     mistranslation of FILTER 2's region check would wrongly include it.
#     Catches M7 (`==` -> `.startswith(...)`).
#   - amount=150.0, region=" EAST" (leading space), channel=STORE: real
#     Pig excludes it (" EAST" != "EAST" exactly, channel != ONLINE); a
#     `.strip()`/`.trim()` mistranslation of FILTER 2's region check
#     would wrongly include it. Catches M5 (adds .strip()/.trim() to
#     every chararray `==`).
#   - amount=150.0, region="east" (lowercase), channel=STORE: real Pig
#     excludes it ("east" != "EAST" exactly, case-sensitive); a
#     `.lower()` mistranslation of FILTER 2's region check would wrongly
#     include it. Catches M4 (adds .lower() to every chararray `==`).
#   - amount=50.0, region=WEST, channel=ONLINE: the ONLY reason real Pig
#     includes this row in qualifying_txn is the `channel == 'ONLINE'`
#     disjunct (amount=50 fails `> 100`, region isn't EAST) — i.e. this
#     row's presence depends on OR meaning OR. Both mutations that touch
#     the OR itself would drop it: M9 (OR -> AND outright) and M3 (the
#     `(A and B) or C` -> `A and (B or C)` precedence flip, since with A
#     false the rewritten form forces the whole thing false regardless
#     of B or C). Catches M3 and M9.
EXTRA_RAW_ROWS = [
    {"amount": 55.25, "region": "NORTH", "channel": "STORE"},
    {"amount": 610.00, "region": "SOUTH", "channel": "ONLINE"},
    {"amount": 18.40, "region": "WEST", "channel": "STORE"},
    {"amount": 245.00, "region": "EAST", "channel": "STORE"},
    {"amount": 0.0, "region": "SOUTH", "channel": "ONLINE"},
    {"amount": 150.0, "region": "EASTX", "channel": "STORE"},
    {"amount": 150.0, "region": " EAST", "channel": "STORE"},
    {"amount": 150.0, "region": "east", "channel": "STORE"},
    {"amount": 50.0, "region": "WEST", "channel": "ONLINE"},
]
EXTRA_CUSTOMERS = [
    {"name": "Nora Byrne", "tier": "SILVER"},
    {"name": "Omar Diaz", "tier": "BRONZE"},
]


def add_extra_rows(raw_rows, cust_by_id):
    base_cust_id = (max(cust_by_id) + 1000) if cust_by_id else 9000
    extra_cust_ids = []
    for i, c in enumerate(EXTRA_CUSTOMERS):
        cid = base_cust_id + i
        cust_by_id[cid] = {"customer_id": cid, **c}
        extra_cust_ids.append(cid)
    for i, r in enumerate(EXTRA_RAW_ROWS):
        raw_rows.append({**r, "customer_id": extra_cust_ids[i % len(extra_cust_ids)]})


def finalize_rows(raw_rows, cust_by_id):
    """Fill the two columns Z3 never solved for: txn_id (sequential — it is
    never a branch input) and customer name (a plain filler, tier is the
    only customer field any FILTER reads)."""
    for i, r in enumerate(raw_rows, start=1):
        r["txn_id"] = i
    for cid, c in cust_by_id.items():
        if not c.get("name"):
            c["name"] = f"Cust_{cid}"  # Z3 never solves for name: not a branch input
        c["customer_id"] = cid
    return raw_rows, cust_by_id


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        for row in rows:
            w.writerow([row[c] for c in columns])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m pipeline.z3gen.gen")
    ap.add_argument("stem", help="e.g. p07_txn_region_tier")
    ap.add_argument("--ir", default=None)
    ap.add_argument("--out-txn", default=None)
    ap.add_argument("--out-customers", default=None)
    args = ap.parse_args(argv)

    ir_path = Path(args.ir) if args.ir else REPO_ROOT / "out" / "ir" / "pig" / f"{args.stem}.node4.json"
    out_txn = Path(args.out_txn) if args.out_txn else REPO_ROOT / "corpus" / "data" / "pig" / "medium_txn.csv"
    out_cust = Path(args.out_customers) if args.out_customers else REPO_ROOT / "corpus" / "data" / "pig" / "medium_customers.csv"

    if not ir_path.is_file():
        print(f"ERROR: no IR at {ir_path} (run pipeline.run_fold pig --file {args.stem} first)", file=sys.stderr)
        return 1

    node4_entries = json.loads(ir_path.read_text(encoding="utf-8"))
    lineage, scenarios, raw_rows, cust_by_id = run(node4_entries)
    add_extra_rows(raw_rows, cust_by_id)
    raw_rows, cust_by_id = finalize_rows(raw_rows, cust_by_id)

    print(f"FILTER conditions found: {len(lineage.filters)}")
    n_legs = 0
    n_both = 0
    seen_legs = {}
    for s in scenarios:
        key = (s["filter"], s["leaf"], tuple(s["guards"]))
        seen_legs.setdefault(key, {})[s["polarity"]] = s["sat"]
        pol = "TRUE " if s["polarity"] else "FALSE"
        verdict = "sat" if s["sat"] else "UNSAT"
        guard_txt = "; ".join(f"{g}={w}" for g, w in s["guards"]) or "(none)"
        print(f"  [{s['filter']}] leaf={s['leaf']!r} guards={guard_txt} want={pol} -> {verdict}")
    for key, pols in seen_legs.items():
        n_legs += 1
        if pols.get(True) and pols.get(False):
            n_both += 1

    print()
    # Fix 5 (honesty restatement): this is deliberately NOT phrased as
    # "branches hit both ways" — that read as full branch/MC/DC coverage,
    # which this script alone does not prove. What IS true, now that
    # Fix 1 chains ancestor FILTER conditions into every solve: each of
    # these leaf conditions is Z3-satisfiable in both polarities, AND
    # every solved row also survives every FILTER upstream of the one it
    # targets — i.e. a real Pig run would actually carry the row that far.
    # Whether it then reaches and is OBSERVED at a DataMatch-compared
    # STORE is proven separately, by the real `pig -x local` run +
    # `python3 -m pipeline.datamatch pig` (see test_z3gen_medium_pig.py).
    print(f"leaf conditions found: {n_legs}")
    print(f"leaf conditions Z3-satisfiable in BOTH polarities, each row surviving "
          f"every upstream FILTER to reach its target: {n_both}/{n_legs}")
    print(f"raw_txn rows written: {len(raw_rows)}  customers rows written: {len(cust_by_id)}")

    write_csv(out_txn, raw_rows, ["txn_id", "amount", "region", "customer_id", "channel"])
    write_csv(out_cust, sorted(cust_by_id.values(), key=lambda r: r["customer_id"]),
              ["customer_id", "name", "tier"])
    print(f"wrote {out_txn}")
    print(f"wrote {out_cust}")

    ok = n_legs > 0 and n_both == n_legs
    print(f"ALL LEAF CONDITIONS Z3-SATISFIABLE IN BOTH POLARITIES (with ancestor "
          f"filters honored): {'true' if ok else 'false'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
