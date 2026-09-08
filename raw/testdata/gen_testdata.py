"""testdata/gen_testdata.py — test data FROM node/4, not from reading the SAS.

Why: exp_009/exp_014 discipline — walk the IR, find every condition that
gates rows (a subsetting IF, a WHERE), split it into legs, and ask Z3 for a
row that makes each leg true and one that makes it false. Add boundary rows
(month = 3 and month = 4 for `month(date) <= 3`; amount equal to the average
for `sale_amount > avg`) and one row per month so GROUP BY has 12 groups.
The rows become the DATALINES of testdata/test_vishnu_testdata.sas — the
file the owner runs in SAS; the SAS output is then diffed against PySpark.

Run:  .venv/bin/python testdata/gen_testdata.py
Reads: out/ir/sas/test_vishnu.node4.json   Writes: testdata/sales_datalines.txt,
       testdata/test_vishnu_testdata.sas, testdata/branches.json
"""
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.term_parse import parse_term  # noqa: E402
from z3 import Int, Real, Solver, And, Or, Not, sat  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
IR = ROOT / "out/ir/sas/test_vishnu.node4.json"

CMP = {"gt": lambda x, y: x > y, "ge": lambda x, y: x >= y, "lt": lambda x, y: x < y,
       "le": lambda x, y: x <= y, "eq": lambda x, y: x == y, "ne": lambda x, y: x != y}


def functor(t): return t[0] if isinstance(t, tuple) else t
def targs(t): return t[1:] if isinstance(t, tuple) else ()


def show(t):
    if isinstance(t, tuple):
        f, a = t[0], t[1:]
        if f == "col": return a[0]
        if f == "lit": return repr(a[0]) if isinstance(a[0], str) else str(a[0])
        if f == "call": return f"{a[0]}({', '.join(show(x) for x in a[1])})"
        if f in CMP: return f"{show(a[0])} {dict(gt='>', ge='>=', lt='<', le='<=', eq='=', ne='^=')[f]} {show(a[1])}"
        if f in ("and", "or"): return f"({show(a[0])} {f} {show(a[1])})"
        if f == "not": return f"not ({show(a[0])})"
        if f == "subquery_expr": return "(SELECT ...)"
        if f == "paren": return f"({show(a[0])})"
    return str(t)


def conditions(node4):
    """every row-gating condition in the IR, with where it came from"""
    out = []
    for rec in node4:
        term = parse_term(rec["term"])
        if functor(term) == "subset_if":
            out.append((rec["block"], rec["seq"], "IF", targs(term)[0]))
        if functor(term) == "create_table_as":
            for core in targs(targs(term)[1])[0]:
                where = targs(core)[3]
                if functor(where) == "some":
                    out.append((rec["block"], rec["seq"], "WHERE", targs(where)[0]))
    return out


def legs(cond, guards=()):
    """split and/or into independently solvable (leaf, guards) legs — exp_009's rule"""
    f = functor(cond)
    if f == "paren": return legs(targs(cond)[0], guards)
    if f == "and":
        a, b = targs(cond)
        return legs(a, guards) + legs(b, guards + ((a, True),))
    if f == "or":
        a, b = targs(cond)
        return legs(a, guards) + legs(b, guards + ((a, False),))
    return [(cond, guards)]


# --- the row model: one sales row is (month, day, amount); the average is a parameter
month, day, amount, avg = Int("month"), Int("day"), Real("amount"), Real("avg")
DOMAIN = And(month >= 1, month <= 12, day >= 1, day <= 28, amount >= 0, amount <= 10000)


def z3_expr(t):
    f = functor(t)
    if f == "lit": return targs(t)[0]
    if f == "col":
        name = targs(t)[0].lower()
        return {"sale_amount": amount, "date": month}[name] if name in ("sale_amount",) else amount
    if f == "call":
        name, args = targs(t)
        if name.lower() == "month": return month
        raise ValueError(f"function not modelled: {name}")
    if f == "subquery_expr": return avg      # the scalar subquery's value, as a parameter
    if f == "paren": return z3_expr(targs(t)[0])
    if f in CMP: return CMP[f](z3_expr(targs(t)[0]), z3_expr(targs(t)[1]))
    if f == "and": return And(z3_expr(targs(t)[0]), z3_expr(targs(t)[1]))
    if f == "or": return Or(z3_expr(targs(t)[0]), z3_expr(targs(t)[1]))
    if f == "not": return Not(z3_expr(targs(t)[0]))
    raise ValueError(f"not modelled: {t}")


def solve(constraints):
    s = Solver(); s.add(DOMAIN, avg == 150, *constraints)
    if s.check() != sat: return None
    m = s.model()
    a = m[amount]
    val = float(a.numerator_as_long()) / float(a.denominator_as_long()) if a is not None else 0.0
    return {"month": m[month].as_long(), "day": m[day].as_long(), "amount": val}


def main():
    node4 = json.loads(IR.read_text())
    report, rows = [], []
    for block, seq, kind, cond in conditions(node4):
        for leaf, guards in legs(cond):
            g = [z3_expr(c) if truth else Not(z3_expr(c)) for c, truth in guards]
            for polarity in (True, False):
                target = z3_expr(leaf) if polarity else Not(z3_expr(leaf))
                row = solve(g + [target])
                report.append({"block": block, "seq": seq, "kind": kind, "condition": show(leaf),
                               "polarity": polarity, "row": row})
                if row: rows.append(row)
    # boundary rows the solver would not pick on its own
    boundaries = [{"month": 3, "day": 31, "amount": 150.0, "why": "month = 3, amount = average: IF keeps it, WHERE > drops it"},
                  {"month": 4, "day": 1, "amount": 149.99, "why": "month = 4: first row IF drops; just under average"},
                  {"month": 12, "day": 31, "amount": 150.01, "why": "just over average"}]
    (ROOT / "testdata/branches.json").write_text(json.dumps({"legs": report, "boundaries": boundaries}, indent=1, default=str))

    # assemble the dataset: Z3 rows + boundaries + one row per month, seeded, then tidy
    rnd = random.Random(42)
    data = []
    for r in rows: data.append((r["month"], min(max(r["day"], 1), 28), round(r["amount"], 2)))
    for b in boundaries: data.append((b["month"], b["day"], b["amount"]))
    for m in range(1, 13):
        data.append((m, rnd.randint(1, 28), float(rnd.choice([50, 75, 120, 130, 175, 210, 260, 300]))))
        if m <= 3: data.append((m, rnd.randint(1, 28), float(rnd.choice([80, 95.5, 140, 199.99]))))
    # force the average to be exactly 150 so the boundary row `amount = average` is real
    data = list(set(data))
    total, n = sum(a for _, _, a in data), len(data)
    fix = 150.0 * (n + 1) - total
    data.append((6, 15, round(fix, 2)))
    assert fix > 0, "fixer row must be a positive amount"
    data = sorted(set(data), key=lambda r: (r[0], r[1]))  # exact duplicates add nothing
    lines = []
    for i, (m, d, a) in enumerate(data, 1):
        amt = ("%d" % a) if a == int(a) else ("%.2f" % a)
        lines.append("%03d %s %02d/%02d/2023" % (i, amt, m, d))
    (ROOT / "testdata/sales_datalines.txt").write_text("\n".join(lines) + "\n")

    src = (ROOT / "corpus/sas/test_vishnu.sas").read_text()
    new_block = "datalines;\n" + "\n".join(lines) + "\n;"
    src2 = re.sub(r"datalines;\n.*?\n;", new_block, src, count=1, flags=re.S)
    header = ("/* exp_42 TEST DATA VERSION of test_vishnu.sas (generated by testdata/gen_testdata.py, 2026-09-05).\n"
              "   Same program, only the DATALINES changed: %d rows, one per branch leg Z3 found in node/4,\n"
              "   plus boundary rows (month 3/4, amount = / just under / just over the average = 150),\n"
              "   plus one row per month so MONTHLY_SALES has 12 groups.\n"
              "   HOW TO RUN: point LIBNAME SALES at a folder you own (SAS OnDemand: e.g. '/home/<your-id>/sales'),\n"
              "   run, and send back the PROC PRINT output at the bottom plus the LOG (the MERGE step logs an ERROR on purpose). */\n\n" % len(lines))
    prints = "\n\n/* ---- exp_42: print every dataset so the output can be compared with PySpark ---- */\n" + "".join(
        "proc print data=sales.%s; title '%s'; run;\n" % (t, t) for t in
        ["sales_data", "total_sales", "avg_sales", "q1_sales", "q1_total_sales", "q1_avg_sales",
         "max_sale", "min_sale", "above_avg_sales", "monthly_sales", "final_summary"])
    (ROOT / "testdata/test_vishnu_testdata.sas").write_text(header + src2 + prints)
    # the corrected variant: the last step written the SAS way that attaches a one-row total to every month
    old_merge = "data sales.final_summary;\n\tmerge sales.monthly_sales(in=a) sales.q1_total_sales(in=b);\nby sale_month;\nrun;"
    assert old_merge in src2, "merge step not found for the fixed variant"
    new_step = ("data sales.final_summary;\n\tif _n_ = 1 then set sales.q1_total_sales;\n\tset sales.monthly_sales;\nrun;")
    fixed_note = ("/* exp_42 FIXED VARIANT (2026-09-05): the original MERGE ... BY sale_month cannot work because\n"
                  "   q1_total_sales has no sale_month column (SAS: ERROR, 0 observations). Step 10 is rewritten as\n"
                  "   IF _N_ = 1 THEN SET q1_total_sales; SET monthly_sales; -- the Q1 total rides along on every month. */\n\n")
    (ROOT / "testdata/test_vishnu_testdata_fixed.sas").write_text(fixed_note + header + src2.replace(old_merge, new_step) + prints)
    print("legs solved: %d  rows: %d  average: %.2f" % (len([r for r in report if r['row']]), len(lines), sum(a for _, _, a in data) / len(data)))
    for r in report:
        print("  %-5s %-6s seq %-2s %-45s %-5s -> %s" % (r["block"], r["kind"], r["seq"], r["condition"], r["polarity"], r["row"]))


if __name__ == "__main__":
    main()
