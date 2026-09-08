"""pipeline.run_pyspark — Phase-D CLI: execute generated PySpark scripts.

Runs out/pyspark/<lang>/<stem>.py under the project .venv's python
(local[1], spark.ui.enabled=false — baked into the generated script's
own header, not passed in here), cwd = repo root so the relative
corpus/... and out/... paths the generator baked in resolve. Every run
appends a record to logs/run_<lang>_<stem>.log (layout law); PySpark
writes its CSV output straight to out/pyspark_out/<lang>/<stem>/<output_name>/
because that is the path pipeline.codegen.pig_pyspark already generated
into the STORE call — this file does not move or rewrite output paths.

CLI:
    python3 -m pipeline.run_pyspark <lang>              # run every generated file
    python3 -m pipeline.run_pyspark <lang> --file STEM  # run just one
        [--scripts-dir out/pyspark/<lang>]  (default derived from <lang>)
        [--venv-python .venv/bin/python]    (default: this repo's .venv)
        [--timeout 600]                     (seconds, per script)

Prints one line per run and exits 0 only if every run's generated
program exited 0.
"""
import argparse
import sys
from pathlib import Path

from pipeline.codegen import common


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m pipeline.run_pyspark")
    ap.add_argument("lang")
    ap.add_argument("--scripts-dir", default=None)
    ap.add_argument("--venv-python", default=None)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--file", default=None, help="run only this stem's generated script")
    args = ap.parse_args(argv)

    lang = args.lang
    scripts_dir = Path(args.scripts_dir) if args.scripts_dir else Path("out/pyspark") / lang
    venv_python = Path(args.venv_python) if args.venv_python else common.DEFAULT_VENV_PYTHON

    if not scripts_dir.is_dir():
        print(f"ERROR: scripts dir not found: {scripts_dir}", file=sys.stderr)
        return 1
    if not venv_python.is_file():
        print(f"ERROR: venv python not found: {venv_python}", file=sys.stderr)
        return 1

    scripts = sorted(scripts_dir.glob("*.py"))
    if args.file:
        scripts = [s for s in scripts if s.stem == args.file]
    if not scripts:
        print(f"ERROR: no *.py files found in {scripts_dir}", file=sys.stderr)
        return 1

    all_ok = True
    rows = []
    for script in scripts:
        stem = script.stem
        result = common.run_generated(
            lang, stem,
            venv_python=venv_python,
            repo_root=common.REPO_ROOT,
            timeout=args.timeout,
        )
        all_ok = all_ok and result["ok"]
        rows.append(result)

    name_w = max(len(r["stem"]) for r in rows)
    for r in rows:
        verdict = "OK" if r["ok"] else "FAIL"
        print(f"{r['stem'].ljust(name_w)}  {verdict}  ({r['duration_s']:.1f}s)  log: {r['log']}")
        if not r["ok"]:
            tail = "\n".join(r["stderr"].splitlines()[-15:])
            print(f"    --- stderr tail ---\n{tail}")

    print()
    print(f"ALL RUNS OK: {'true' if all_ok else 'false'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
