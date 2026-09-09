"""loops/gen_block_testdata.py — test data for ONE block at a time, from node/4 (exp_42, 2026-09-07).

Why: loop 3 runs every SAS step in isolation, on inputs made for that step alone,
so a wrong step cannot hide behind a right upstream one. For each block that
creates a dataset, this walks the SAS node/4, finds the block's input datasets and
their schemas (inferred the way the interpreters infer them), and generates rows:
  * one Z3 row per leg of every IF / WHERE in the block, true and false
    (exp_009's rule: split and/or into legs, solve each with the others as guards),
  * boundary rows: the compared expression equal to, one below and one above the constant,
  * seeded random rows, one per month for date columns so GROUP BY has many groups,
  * a one-row dataset with a fixed value for every input read through a scalar subquery.
The model is general over the schema: a numeric column is a Real, a date column is
(year, month, day) integers so MONTH()/YEAR()/DAY() are just those variables, a
character column is random text. Nothing here knows the program's column names.

Run:   .venv/bin/python loops/gen_block_testdata.py <stem>            (node/4 from out/ir/sas/<stem>.node4.json)
Writes: out/loops/blocks/<stem>/<block>/in/<lib.name>.csv + .schema.json, and manifest.json
        {block, creates: [...], inputs: [...], conditions: [...]} per block.
"""
import datetime
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.term_parse import parse_term  # noqa: E402
from z3 import Int, Real, Solver, And, Or, Not, sat, RealVal  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CMP = {"gt": lambda x, y: x > y, "ge": lambda x, y: x >= y, "lt": lambda x, y: x < y,
       "le": lambda x, y: x <= y, "eq": lambda x, y: x == y, "ne": lambda x, y: x != y}
AGG = {"sum", "avg", "mean", "max", "min", "count"}
EPOCH = datetime.date(1960, 1, 1)


def functor(t): return t[0] if isinstance(t, tuple) else t
def targs(t): return t[1:] if isinstance(t, tuple) else ()
def low(a): return a.lower() if isinstance(a, str) else a


def ds_key(d):
    a = targs(d)
    return f"{low(a[0])}.{low(a[1])}" if len(a) == 2 else f"work.{low(a[0])}"


# ------------------------------------------------------------ schema inference (mirrors sas_interp.pl)
class Schemas:
    def __init__(self):
        self.cols = {}      # key -> [(name, type)]
        self.formats = {}   # column name -> format

    def expr_type(self, e, cols):
        f = functor(e)
        if f == "col":
            return dict(cols).get(low(targs(e)[0]), "num")
        if f == "call" and low(targs(e)[0]) in ("max", "min"):
            return self.expr_type(targs(e)[1][0], cols)
        if f == "lit":
            return "num" if isinstance(targs(e)[0], (int, float)) else "char"
        return "num"

    def step(self, terms):
        head = terms[0]
        if functor(head) == "data":
            k = ds_key(targs(head)[0]); body = terms[1:]
            for t in body:
                if functor(t) == "format":
                    self.formats[low(targs(t)[0])] = targs(targs(t)[1])[0] + "."
            by = {functor(t): t for t in body}
            if "input" in by and "datalines" in by:
                cols = []
                for v in targs(by["input"])[0]:
                    n = low(targs(v)[0])
                    cols.append((n, "char" if functor(v) == "cvar" else ("date" if functor(targs(v)[1]) == "some" else "num")))
                self.cols[k] = cols
            elif "if_then_set" in by and "set" in by:
                self.cols[k] = union(self.cols.get(ds_key(targs(by["set"])[0]), []) + self.cols.get(ds_key(targs(by["if_then_set"])[2]), []))
            elif "set" in by:
                self.cols[k] = list(self.cols.get(ds_key(targs(by["set"])[0]), []))
            elif "merge" in by:
                self.cols[k] = union([c for s in targs(by["merge"])[0] for c in self.cols.get(ds_key(targs(s)[0]), [])])
        elif functor(head) == "proc_sql":
            for t in terms[1:]:
                if functor(t) == "create_table_as":
                    k = ds_key(targs(t)[0]); core = targs(targs(t)[1])[0][0]
                    self.cols[k] = self.core_cols(core)

    def core_cols(self, core):
        projs, frm = targs(core)[0], targs(core)[1]
        incols = self.from_cols(frm)
        out = []
        for p in projs:
            e, a = targs(p)
            if functor(e) == "star":
                out += incols
            elif functor(a) == "some":
                out.append((low(targs(a)[0]), self.expr_type(e, incols)))
            elif functor(e) == "col":
                out.append((low(targs(e)[0]), self.expr_type(e, incols)))
            else:
                out.append(("_auto", self.expr_type(e, incols)))
        return out

    def from_cols(self, frm):
        if functor(frm) == "table":
            return list(self.cols.get(ds_key(targs(frm)[0]), []))
        return self.core_cols(targs(frm)[0])


def union(cols):
    out, seen = [], set()
    for n, t in cols:
        if n not in seen:
            out.append((n, t)); seen.add(n)
    return out


# ------------------------------------------------------------ what a block reads and gates on
def block_inputs(terms):
    """-> (reads: [key], scalar_reads: [key], conditions: [(kind, expr, from_key)], creates: [key])"""
    reads, scalars, conds, creates = [], [], [], []
    head = terms[0]
    if functor(head) == "data":
        creates.append(ds_key(targs(head)[0]))
        for t in terms[1:]:
            f = functor(t)
            if f == "set": reads.append(ds_key(targs(t)[0]))
            if f == "if_then_set": reads.append(ds_key(targs(t)[2]))
            if f == "merge": reads += [ds_key(targs(s)[0]) for s in targs(t)[0]]
            if f == "subset_if": conds.append(("IF", targs(t)[0], reads[0] if reads else None))
    elif functor(head) == "proc_sql":
        for t in terms[1:]:
            if functor(t) == "create_table_as":
                creates.append(ds_key(targs(t)[0]))
                core = targs(targs(t)[1])[0][0]
                frm = targs(core)[1]
                while functor(frm) == "subquery":
                    frm = targs(targs(frm)[0])[1]
                src = ds_key(targs(frm)[0]); reads.append(src)
                where = targs(core)[3]
                if functor(where) == "some":
                    conds.append(("WHERE", targs(where)[0], src))
                    for sub in subterms(targs(where)[0]):
                        if functor(sub) == "subquery_expr":
                            scalars.append(ds_key(targs(targs(targs(sub)[0])[1])[0]))
    return uniq(reads), uniq(scalars), conds, creates


def subterms(t):
    yield t
    if isinstance(t, tuple):
        for a in t[1:]:
            yield from subterms(a)
    elif isinstance(t, list):
        for a in t:
            yield from subterms(a)


def uniq(xs):
    out = []
    for x in xs:
        if x not in out: out.append(x)
    return out


def legs(cond, guards=()):
    f = functor(cond)
    if f == "paren": return legs(targs(cond)[0], guards)
    if f == "and":
        a, b = targs(cond); return legs(a, guards) + legs(b, guards + ((a, True),))
    if f == "or":
        a, b = targs(cond); return legs(a, guards) + legs(b, guards + ((a, False),))
    return [(cond, guards)]


# ------------------------------------------------------------ the Z3 row model, general over a schema
class RowModel:
    def __init__(self, cols, scalar_values):
        self.vars, self.domain = {}, []
        for n, t in cols:
            if t == "num":
                self.vars[n] = Real(n); self.domain.append(And(self.vars[n] >= 0, self.vars[n] <= 10000))
            elif t == "date":
                y, m, d = Int(n + "_y"), Int(n + "_m"), Int(n + "_d")
                self.vars[n] = (y, m, d)
                self.domain += [y == 2023, m >= 1, m <= 12, d >= 1, d <= 28]
        self.scalars = scalar_values   # key -> value of the one-row dataset read by a subquery
        self.cols = cols

    def z3(self, t):
        f = functor(t)
        if f == "lit": return targs(t)[0]
        if f == "paren": return self.z3(targs(t)[0])
        if f == "col":
            v = self.vars.get(low(targs(t)[0]))
            if v is None: raise ValueError("column not modelled: " + str(t))
            return v if not isinstance(v, tuple) else v[0] * 10000 + v[1] * 100 + v[2]
        if f == "call":
            name, args = low(targs(t)[0]), targs(t)[1]
            if name in ("month", "year", "day"):
                v = self.vars.get(low(targs(args[0])[0]))
                if not isinstance(v, tuple): raise ValueError("not a date: " + str(args[0]))
                return {"year": v[0], "month": v[1], "day": v[2]}[name]
            raise ValueError("function not modelled: " + name)
        if f == "subquery_expr":
            src = ds_key(targs(targs(targs(t)[0])[1])[0])
            return RealVal(self.scalars[src])
        if f in CMP: return CMP[f](self.z3(targs(t)[0]), self.z3(targs(t)[1]))
        if f == "and": return And(self.z3(targs(t)[0]), self.z3(targs(t)[1]))
        if f == "or": return Or(self.z3(targs(t)[0]), self.z3(targs(t)[1]))
        if f == "not": return Not(self.z3(targs(t)[0]))
        raise ValueError("not modelled: " + str(t))

    def solve(self, constraints, rnd):
        s = Solver(); s.add(*self.domain, *constraints)
        if s.check() != sat: return None
        m = s.model()
        row = {}
        for n, t in self.cols:
            v = self.vars.get(n)
            if t == "num":
                x = m.eval(v, model_completion=True)
                row[n] = round(float(x.numerator_as_long()) / float(x.denominator_as_long()), 2)
            elif t == "date":
                row[n] = tuple(m.eval(p, model_completion=True).as_long() for p in v)
            else:
                row[n] = rnd.choice(["A", "B", "C"])
        return row

    def random_row(self, rnd, month=None):
        row = {}
        for n, t in self.cols:
            if t == "num": row[n] = float(rnd.choice([50, 75, 120, 130, 175, 210, 260, 300, 199.99]))
            elif t == "date": row[n] = (2023, month or rnd.randint(1, 12), rnd.randint(1, 28))
            else: row[n] = "%03d" % rnd.randint(1, 999)
        return row


def boundary_constraints(model, leaf):
    """for `lhs OP rhs` with a constant/scalar rhs: lhs == rhs, rhs - 1, rhs + 1"""
    f = functor(leaf)
    if f not in CMP: return []
    lhs, rhs = targs(leaf)
    if functor(rhs) not in ("lit", "subquery_expr"): return []
    r = model.z3(rhs); l = model.z3(lhs)
    return [l == r, l == r - 1, l == r + 1]


# ------------------------------------------------------------ CSV in the interpreters' convention
def fmt_num(v):
    if float(v) == int(v) and abs(v) < 1e15: return str(int(v))
    return "%.12g" % v


def sas_days(y, m, d): return (datetime.date(y, m, d) - EPOCH).days


def cell(v, t, fmt):
    if v is None: return "."
    if t == "date":
        y, m, d = v
        return "%02d/%02d/%d" % (m, d, y) if (fmt or "").lower().startswith("mmddyy") else str(sas_days(y, m, d))
    if t == "num": return fmt_num(v)
    return str(v)


def write_dataset(d, key, cols, rows, formats):
    d.mkdir(parents=True, exist_ok=True)
    lines = [",".join(n for n, _ in cols)] + [",".join(cell(r[n], t, formats.get(n)) for n, t in cols) for r in rows]
    (d / (key + ".csv")).write_text("\r\n".join(lines) + "\r\n")
    (d / (key + ".schema.json")).write_text(json.dumps({"columns": [{"name": n, "type": t, "format": formats.get(n) if t == "date" else None} for n, t in cols]}, indent=1))


def main(stem, node4_path=None, out_root=None):
    node4 = json.loads(Path(node4_path or ROOT / f"out/ir/sas/{stem}.node4.json").read_text())
    blocks = {}
    for rec in node4:
        blocks.setdefault(rec["block"], []).append((rec["seq"], parse_term(rec["term"])))
    schemas = Schemas()
    out_root = Path(out_root) if out_root else ROOT / "out/loops/blocks" / stem
    manifest = []
    for b, items in blocks.items():
        terms = [t for _, t in sorted(items)]
        reads, scalars, conds, creates = block_inputs(terms)
        if creates:
            rnd = random.Random(int(b.split('_')[-1]))   # deterministic: hash() of a str changes per process
            scalar_values = {k: 150.0 for k in scalars}
            entry = {"block": b, "creates": creates, "inputs": reads + [s for s in scalars if s not in reads], "conditions": [], "rows": {}}
            for key in entry["inputs"]:
                cols = schemas.cols.get(key)
                if cols is None:
                    print(f"  {b}: input {key} has no schema yet — skipped"); continue
                if key in scalar_values and key not in reads:
                    rows = [{n: (scalar_values[key] if t == "num" else None) for n, t in cols}]
                else:
                    model = RowModel(cols, scalar_values)
                    rows = []
                    for kind, cond, src in conds:
                        if src != key: continue
                        for leaf, guards in legs(cond):
                            g = [model.z3(c) if truth else Not(model.z3(c)) for c, truth in guards]
                            for polarity in (True, False):
                                target = model.z3(leaf) if polarity else Not(model.z3(leaf))
                                row = model.solve(g + [target], rnd)
                                entry["conditions"].append({"kind": kind, "leg": str(leaf), "polarity": polarity, "row": row})
                                if row: rows.append(row)
                            for bc in boundary_constraints(model, leaf):
                                row = model.solve(g + [bc], rnd)
                                if row: rows.append(row)
                    has_date = any(t == "date" for _, t in cols)
                    for i in range(12 if has_date else 8):
                        rows.append(model.random_row(rnd, month=i + 1 if has_date else None))
                    # a merge/BY key column gets overlapping small integers so keys match across sources
                    for n, t in cols:
                        if t == "num" and (n.endswith("_month") or n in ("key", "id")):
                            for i, r in enumerate(rows): r[n] = float(i % 6 + 1)
                    seen, dedup = set(), []
                    for r in rows:
                        sig = json.dumps(r, sort_keys=True)
                        if sig not in seen: seen.add(sig); dedup.append(r)
                    rows = dedup
                write_dataset(out_root / b / "in", key, cols, rows, schemas.formats)
                entry["rows"][key] = len(rows)
            (out_root / b / "in").mkdir(parents=True, exist_ok=True)
            manifest.append(entry)
        schemas.step(terms)
    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=1, default=str))
    for e in manifest:
        print(f"  {e['block']:6} creates {','.join(e['creates']):28} inputs {', '.join(f'{k}({n})' for k, n in e['rows'].items()) or '-'}")
    print(f"wrote {out_root}/manifest.json ({len(manifest)} blocks)")


if __name__ == "__main__":
    # gen_block_testdata.py [stem] [node4.json] [out_dir]   (the studio API passes all three)
    main(sys.argv[1] if len(sys.argv) > 1 else "test_vishnu_testdata", *sys.argv[2:4])
