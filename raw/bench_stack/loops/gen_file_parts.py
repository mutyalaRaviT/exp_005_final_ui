"""loops/gen_file_parts.py — the file-level parts: four quarters and the full file (exp_42, 2026-09-07).

Why: loop 4 runs the WHOLE program on five datasets: the DATALINES rows split
into four quarters (rows 1-n/4, ...) and the full set. Every part goes through
the same pipeline as any corpus file (tokenise, fold, codegen, Rust, both
interpreters, Spark), and the receipts add one check no single run can give:
the quarter results must add up to the full-file result for every SUM and
COUNT (a partition test — an aggregate that is not decomposable shows here).

Run:    .venv/bin/python loops/gen_file_parts.py [stem]     (default test_vishnu_testdata)
Writes: corpus/parts/<stem>_q1.sas .. _q4.sas, <stem>_full.sas
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
stem = sys.argv[1] if len(sys.argv) > 1 else "test_vishnu_testdata"
src = (ROOT / "corpus/sas" / (stem + ".sas")).read_text()
m = re.search(r"datalines;\n(.*?)\n;", src, flags=re.S)
rows = [l for l in m.group(1).split("\n") if l.strip()]
n = len(rows)
bounds = [round(i * n / 4) for i in range(5)]
parts = {f"q{i + 1}": rows[bounds[i]:bounds[i + 1]] for i in range(4)}
parts["full"] = rows
out = ROOT / "corpus/parts"
out.mkdir(exist_ok=True)
for name, part in parts.items():
    text = src[:m.start(1)] + "\n".join(part) + src[m.end(1):]
    header = f"/* exp_42 loop 4 part {name}: {len(part)} of {n} DATALINES rows of {stem}.sas (loops/gen_file_parts.py, 2026-09-07) */\n"
    (out / f"{stem}_{name}.sas").write_text(header + text)
    print(f"wrote corpus/parts/{stem}_{name}.sas ({len(part)} rows)")
