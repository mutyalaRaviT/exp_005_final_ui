#!/usr/bin/env python3
"""tools/xcheck_datamatch.py — Task 11 step 5: Rust's DataMatch against Python's, on real CSVs.

Why this exists. `backend/rust_inferred_duckdb/src/datamatch.rs` is the one module in the
slice where a wrong answer is silent: a comparison that is too generous returns `match`
over a bad migration and the loop reports green. Three unit tests cover the three ways
that happens in the abstract; this covers it on the data the loop actually judges — the
left/right CSVs of every table-writing block of the exp_42 fixture, as written by
`server/bench_receipt.py` (the Step 0 receipt) or by `POST /api/run`.

Inputs -> outputs. a blocks directory (`raw/bench_stack/out/api/<stem>/blocks`, or the
Step-0 snapshot `out/xcheck_baseline_<date>`) laid out as `<block>/{rust|prolog}/<table>.csv`
beside `<block>/spark/<table>.csv` -> one line per block naming both implementations'
`(verdict, n_mismatch)`, and exit 1 on any disagreement. Python is the reference: where
they differ, Rust is wrong (task-11-brief.md step 5).

Run:  raw/bench_stack/.venv/bin/python tools/xcheck_datamatch.py [--blocks DIR] [--left rust|prolog]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "raw/bench_stack"
STORE = REPO / "backend/target/release/lineageq_store"
sys.path.insert(0, str(BENCH))
from pipeline.datamatch import compare_rows as py_compare  # noqa: E402


def read_csv(p):
    import csv
    with open(p, newline="") as fh:
        return list(csv.reader(fh))


def rust_compare(left, right):
    out = subprocess.run([str(STORE), "datamatch", str(left), str(right)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"lineageq_store datamatch failed on {left}: {out.stderr}")
    d = json.loads(out.stdout)
    return d["verdict"], d["n_mismatch"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", default=str(BENCH / "out/xcheck_baseline_2026-09-10"),
                    help="a <block>/{rust,spark}/<table>.csv tree")
    ap.add_argument("--left", default="rust", choices=["rust", "prolog"])
    a = ap.parse_args()
    root = Path(a.blocks)
    if not root.is_dir():
        raise SystemExit(f"no blocks directory at {root}")
    n_ok = n_all = 0
    bad = []
    for bdir in sorted(d for d in root.iterdir() if d.is_dir()):
        ldir, rdir = bdir / a.left, bdir / "spark"
        if not ldir.is_dir() or not rdir.is_dir():
            continue
        for lcsv in sorted(ldir.glob("*.csv")):
            rcsv = rdir / lcsv.name
            if not rcsv.exists():
                print(f"  {bdir.name:6} {lcsv.stem:28} right CSV missing — skipped")
                continue
            n_all += 1
            pv, pn, _ = py_compare(read_csv(lcsv)[1:], read_csv(rcsv)[1:])
            rv, rn = rust_compare(lcsv, rcsv)
            same = (pv == rv) and (pn == rn)
            n_ok += same
            if not same:
                bad.append((bdir.name, lcsv.stem, pv, pn, rv, rn))
            print(f"  {bdir.name:6} {lcsv.stem:28} python ({pv},{pn})  rust ({rv},{rn})  {'identical' if same else 'DISAGREE'}")
    print(f"xcheck  {n_ok}/{n_all} identical (left={a.left}, {root})")
    if bad or n_all == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
