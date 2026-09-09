"""server/bench_receipt.py — the Bench's receipt line for run_all.sh (exp_42, 2026-09-08).

Why: the Bench runs one block at a time on request; run_all.sh needs the same
proof headless, in one line, so the workbench is covered by the loop's receipts.
For every table-writing block of a program: left = the executable node/4 (Rust
interpreter, or Prolog with --engine prolog), right = the block's own PySpark
program on local Spark, both on the block's Z3 inputs, judged by DataMatch —
exactly what bench_api.run_block does for the page.

Run:  .venv/bin/python server/bench_receipt.py [corpus/sas/test_vishnu_testdata.sas] [--engine rust|prolog|both]
Prints one line per block and one receipt line; writes out/bench/receipts.txt.
Exit code 0 when every block matches (match-warn counts: a block whose Z3 inputs
yield 0 rows is agreed empty on both sides).
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from server import bench_api as bench  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="corpus/sas/test_vishnu_testdata.sas")
    ap.add_argument("--engine", default="rust", choices=["rust", "prolog", "both"])
    a = ap.parse_args()
    engines = ["rust", "prolog"] if a.engine == "both" else [a.engine]
    prog = bench.open_program(path=a.path)
    stem = prog["stem"]
    blocks = [b for b in prog["blocks"] if b["writes"]]
    lines, all_ok = [], True
    for eng in engines:
        n_ok = 0
        t0 = time.time()
        for b in blocks:
            r = bench.run_block(stem, b["id"], eng)
            ok = r["match"] in ("match", "match-warn")
            n_ok += ok
            all_ok &= ok
            lines.append(f"    {stem} {b['id']} {b['name']:<24} {eng} interp {r['left']['ms'] if r['left'] else '-':>7} ms · spark {r['right']['ms'] if r['right'] else '-':>8} ms · {r['match']}")
        lines.append(f"    bench  {n_ok}/{len(blocks)} blocks match ({eng} interp == spark, Z3 inputs, {time.time() - t0:.0f} s)")
    out = "\n".join(lines)
    print(out)
    bench.BENCH.mkdir(parents=True, exist_ok=True)
    (bench.BENCH / "receipts.txt").write_text(out + "\n")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
