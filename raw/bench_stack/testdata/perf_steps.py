"""exp_42 2026-09-08 — time every step of convert() + open_program() for one file, on its own.
Usage: python3 testdata/perf_steps.py big_1000
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
stem = sys.argv[1]
PY = ROOT / ".venv/bin/python"
RUST = ROOT / "rust_engine/target/release/lineageq_sas"
work = ROOT / "out/api" / stem
corpus = work / "corpus"
corpus.mkdir(parents=True, exist_ok=True)
(corpus / f"{stem}.sas").write_text((ROOT / "corpus/sas" / f"{stem}.sas").read_text())
node4_pl = work / "ir" / f"{stem}.node4.pl"

steps = [
    ("1 tokenise (python)", [str(PY), "-m", "pipeline.run_tokenise", "sas", "--dir", str(corpus)]),
    ("2 fold + round trip -> node/4 (python driver + swipl)", [str(PY), "-m", "pipeline.run_fold", "sas", "--file", stem, "--out-dir", str(work / "ir"), "--work-dir", str(work / "work")]),
    ("3 prolog codegen (swipl)", ["swipl", "-q", "-s", "codegen/sas_pyspark.pl", "-g", "main", "--", str(node4_pl), "codegen/sas_runtime_preamble.py", str(work / f"{stem}_ravi_prolog.py")]),
    ("4 rust: fold + unfold + node/4 + pyspark + pretty", [str(RUST), "out/spec/sas.json", str(corpus / f"{stem}.sas"), str(work / "rust"), "codegen/sas_runtime_preamble.py", "codegen/sas_runtime_pretty.py"]),
    ("5 prolog pretty (swipl)", ["swipl", "-q", "-s", "codegen/sas_pyspark_pretty.pl", "-g", "main", "--", str(node4_pl), "codegen/sas_runtime_pretty.py", str(work / f"{stem}_pretty_prolog.py")]),
    ("6 rust lineage", [str(RUST), "lineage", "out/spec/sas.json", str(corpus / f"{stem}.sas"), str(work / "lineage" / "sas.rust.pl")]),
]
(work / "lineage").mkdir(exist_ok=True)
total = 0
for name, cmd in steps:
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    dt = time.time() - t0
    total += dt
    print(f"{dt:7.1f}s  {name}  rc={p.returncode}")
print(f"{total:7.1f}s  total")
