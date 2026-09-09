"""loops/extract_pyspark_body.py — the job part of a generated PySpark program.

Why: the runtime preamble (function definitions, pasted at the top of every
generated program) is not the job; the statements after its closing
`# =====` line are. This copies that part to corpus/pyspark/<stem>.py so the
PySpark pyDSL parses only job statements.

Run:  .venv/bin/python loops/extract_pyspark_body.py out/pyspark/*_ravi_prolog.py
Writes: corpus/pyspark/<stem>.py   (stem without the _ravi_prolog suffix)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARK = "# ====="

for arg in sys.argv[1:]:
    src = Path(arg).read_text()
    lines = src.splitlines(keepends=True)
    last = max(i for i, l in enumerate(lines) if l.startswith(MARK))
    body = "".join(lines[last + 1:]).lstrip("\n")
    stem = Path(arg).stem.replace("_ravi_prolog", "").replace("_ravi_rust", "")
    out = ROOT / "corpus/pyspark" / (stem + ".py")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body)
    print("wrote", out, len(body.splitlines()), "lines")
