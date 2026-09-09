"""loops/report.py — the receipts for loops 3 and 4, plus the timing table (exp_42, 2026-09-07).

Why: three executors (Prolog interpreter, Rust interpreter, Spark) wrote CSVs for
every block and every file part. This reads them back and says, per table, whether
the three agree byte for byte, or as row sets, or not at all; then checks that the
four quarters add up to the full file for every SUM / COUNT / MAX / MIN the program
computes (a partition test); then prints Prolog-vs-Rust wall clock per loop from
out/loops/timings.csv (loop,engine,item,ms — appended by loops/run_loops.sh).

Run:  .venv/bin/python loops/report.py [stem ...]     (default: test_vishnu_testdata test_vishnu_testdata_fixed)
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.term_parse import parse_term  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXECUTORS = ["prolog", "rust", "spark"]


def read_csv(p):
    if not p.exists():
        return None
    with open(p, newline="") as fh:
        return list(csv.reader(fh))


def verdict(tables):
    """tables: {executor: rows or None} -> (verdict, note)"""
    present = {e: t for e, t in tables.items() if t is not None}
    if len(present) < len(tables):
        return "MISSING", "no output from " + ", ".join(e for e in tables if tables[e] is None)
    ref = next(iter(present.values()))
    if all(t == ref for t in present.values()):
        return "PASS bytes", ""
    if all(t[0] == ref[0] and Counter(map(tuple, t[1:])) == Counter(map(tuple, ref[1:])) for t in present.values()):
        return "PASS rows", "same rows, different order"
    notes = []
    for e, t in present.items():
        if t != ref:
            notes.append(f"{e}: {len(t) - 1} rows vs {len(ref) - 1}")
    return "FAIL", "; ".join(notes)


def report_blocks(stem):
    root = ROOT / "out/loops/blocks" / stem
    manifest = json.loads((root / "manifest.json").read_text())
    print(f"\nLoop 3 — block level, {stem}: every step on its own generated inputs, three executors")
    print(f"  {'block':7} {'creates':26} {'inputs':>6} {'rows':>5}  verdict")
    worst = "PASS bytes"
    for e in manifest:
        for k in e["creates"]:
            tables = {x: read_csv(root / e["block"] / x / (k + ".csv")) for x in EXECUTORS}
            v, note = verdict(tables)
            rows = len(tables["prolog"]) - 1 if tables["prolog"] else "-"
            print(f"  {e['block']:7} {k:26} {sum(e['rows'].values()):6} {rows:>5}  {v}  {note}")
            worst = v if v == "FAIL" or (v == "MISSING" and worst != "FAIL") else worst
    return worst


def report_parts(stem):
    root = ROOT / "out/loops/parts"
    parts = ["q1", "q2", "q3", "q4", "full"]
    print(f"\nLoop 4 — file level, {stem}: four quarters + the full file, three executors")
    tables = sorted(p.name[:-4] for p in (root / "interp_prolog" / f"{stem}_full").glob("*.csv"))
    print(f"  {'table':26} " + " ".join(f"{p:>10}" for p in parts))
    worst = "PASS bytes"
    for t in tables:
        cells = []
        for p in parts:
            got = {"prolog": read_csv(root / "interp_prolog" / f"{stem}_{p}" / (t + ".csv")),
                   "rust": read_csv(root / "interp_rust" / f"{stem}_{p}" / (t + ".csv")),
                   "spark": read_csv(root / "spark" / f"{stem}_{p}" / (t + ".csv"))}
            v, _ = verdict(got)
            n = len(got["prolog"]) - 1 if got["prolog"] else "-"
            cells.append(f"{v.split()[0]}({n})")
            worst = v if v == "FAIL" or (v == "MISSING" and worst != "FAIL") else worst
        print(f"  {t:26} " + " ".join(f"{c:>10}" for c in cells))
    quarter_sums(stem, root, parts)
    return worst


def num(s):
    try:
        return float(s)
    except ValueError:
        return None


def quarter_sums(stem, root, parts):
    """every SUM/COUNT/MAX/MIN a CREATE TABLE computes (grouped or not): the full file's value
    must be the sum (or max/min) of the quarters' values, key by key"""
    node4 = json.loads((ROOT / "out/ir/parts" / f"{stem}_full.node4.json").read_text())
    print("  quarters add up to the full file (partition test):")
    ok = True
    for rec in node4:
        t = parse_term(rec["term"])
        if not (isinstance(t, tuple) and t[0] == "create_table_as"):
            continue
        ds, core = t[1], t[2][1][0]          # create_table_as(ds, select_stmt([core|_], order, limit))
        key = f"{ds[1].lower()}.{ds[2].lower()}"
        projs, group = core[1], core[5]
        grouped = group != "none"
        rows = {p: read_csv(root / "interp_prolog" / f"{stem}_{p}" / (key + ".csv")) for p in parts}
        if any(r is None for r in rows.values()):
            continue
        header = rows["full"][0]
        for i, proj in enumerate(projs):
            e = proj[1]
            if not (isinstance(e, tuple) and e[0] == "call" and e[1].lower() in ("sum", "count", "max", "min")):
                continue
            fn = e[1].lower()
            col = header[i]
            nkeys = len(group[1]) if grouped else 0
            by_key = defaultdict(list)
            for p in parts[:4]:
                for r in rows[p][1:]:
                    v = num(r[i])
                    if v is not None:
                        by_key[tuple(r[:nkeys])].append(v)
            full = {tuple(r[:nkeys]): num(r[i]) for r in rows["full"][1:]}
            combine = {"sum": sum, "count": sum, "max": max, "min": min}[fn]
            bad = [k for k, v in full.items() if v is None or k not in by_key or abs(combine(by_key[k]) - v) > 1e-6]
            state = "ok" if not bad and set(full) == set(by_key) else f"MISMATCH {bad[:3]}"
            ok = ok and state == "ok"
            sample = next(iter(full.items())) if full else ("", None)
            print(f"    {key:26} {fn.upper()}({col}){' by key' if grouped else ''}: {len(full)} value(s), e.g. {sample[1]} = {fn}({[round(x, 2) for x in by_key.get(sample[0], [])]})  {state}")
    return ok


def timings():
    p = ROOT / "out/loops/timings.csv"
    if not p.exists():
        return
    rows = list(csv.reader(open(p)))
    agg = defaultdict(float)
    items = defaultdict(int)
    for loop, engine, item, ms in rows:
        agg[(loop, engine)] += float(ms)
        items[(loop, engine)] += 1
    print("\nWall clock per loop (ms, whole process incl. start-up; Rust is one binary, Prolog is swipl + consult per call)")
    print(f"  {'loop':44} {'prolog':>10} {'rust':>10} {'spark':>10}")
    for loop in sorted({l for l, _ in agg}):
        cells = [f"{agg[(loop, e)]:.0f} ({items[(loop, e)]})" if (loop, e) in agg else "-" for e in EXECUTORS]
        print(f"  {loop:44} " + " ".join(f"{c:>10}" for c in cells))


if __name__ == "__main__":
    stems = sys.argv[1:] or ["test_vishnu_testdata", "test_vishnu_testdata_fixed"]
    verdicts = {}
    for stem in stems:
        if (ROOT / "out/loops/blocks" / stem / "manifest.json").exists():
            verdicts[f"loop3 {stem}"] = report_blocks(stem)
        if (ROOT / "out/loops/parts/interp_prolog" / f"{stem}_full").exists():
            verdicts[f"loop4 {stem}"] = report_parts(stem)
    timings()
    print("\nVerdicts: " + "; ".join(f"{k}: {v}" for k, v in verdicts.items()))
