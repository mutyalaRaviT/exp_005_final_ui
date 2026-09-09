"""pipeline.z3gen.pig_semantics — what every Pig node/4 functor a FILTER
condition can be built from MEANS, in Z3. One line per functor.

Why this file exists (ported design, not ported code, from
exp_009_executable_ast/spike/sas_semantics.py): a Z3 test-data engine for
an IR needs exactly one table that says what each functor DOES, so the
engine that walks the IR never has to change when a new script uses one
more functor. exp_009 proved this for SAS PROC SQL's node/3 IR (~30
functors, one table, ~110 lines); this file is the same discipline for
this repo's Pig node/4 IR, scoped to the functors a FILTER's boolean
condition can actually contain per pipeline/specs/pig.py's EXPR_LADDER —
comparisons and booleans. `pipeline.z3gen.gen` (the ENGINE) reads CMP and
BOOL below by functor name; it never spells out "gt" or "and" itself.
Growing this table to cover a script that filters on arithmetic (e.g.
`(amount - fee) > 0`) is ONE new line in ARITH below plus wiring it into
`gen.eval_expr`'s existing generic dispatch — no new branch-walking logic.

Scope note: Pig aggregates (SUM/COUNT/AVG) and arithmetic (add/sub/mul/
div/neg) are VALUE-producing, never branch-gating, in every corpus
script written so far (p01-p07) — a FILTER's condition is always a
comparison or a boolean combination of comparisons, never "does this sum
exceed 100" (that would need GROUP+HAVING, which this grammar subset does
not have). They are still named here, and marked with z3=None, so the
"one line per functor, nothing implicit" rule holds even for the
functors this engine does not currently need to branch on.
"""
from z3 import And, Or, Not

# ---------------------------------------------------------------------
# comparisons — the leaves of every FILTER condition tree. `x`, `y` are
# already-built Z3 terms (Real, Int, or String, whichever the column's
# Pig type maps to — see gen.PIG_TYPE_TO_Z3).
CMP = {
    "gt": lambda x, y: x > y,
    "ge": lambda x, y: x >= y,
    "lt": lambda x, y: x < y,
    "le": lambda x, y: x <= y,
    "eq": lambda x, y: x == y,
    "ne": lambda x, y: x != y,
}

# ---------------------------------------------------------------------
# booleans — how a FILTER condition combines comparisons. `leaves` says
# how gen.leaves() splits a compound into independently-solvable legs,
# exactly mirroring exp_009's edges.pl / gen.py `leaves()` convention:
# the right side of AND is only reachable (as its own leg) once the left
# side is already known true; the right side of OR, once the left side
# is already known false.
BOOL = {
    "and": lambda x, y: And(x, y),
    "or": lambda x, y: Or(x, y),
    "not": lambda x: Not(x),
}
BOOL_LEAF_GUARD = {"and": True, "or": False}  # required truth of the LEFT
                                               # child before the RIGHT
                                               # child's own leg is reached

# `paren(E)` is not a boolean combinator — it is source-fidelity
# bookkeeping the printer needs to reproduce the user's own parentheses
# (see pipeline/specs/pig.py's EXPR_FORMS "paren" entry). Meaning-wise it
# is the identity function; gen.py unwraps it before dispatch.
TRANSPARENT = {"paren"}

# ---------------------------------------------------------------------
# arithmetic and aggregates: documented, not wired (see module docstring).
ARITH = {
    "add": lambda x, y: x + y,
    "sub": lambda x, y: x - y,
    "mul": lambda x, y: x * y,
    "div": lambda x, y: x / y,
    "neg": lambda x: -x,
}
AGG = {"SUM": "sum of the group's rows", "COUNT": "count of the group's rows",
       "AVG": "average of the group's rows"}
