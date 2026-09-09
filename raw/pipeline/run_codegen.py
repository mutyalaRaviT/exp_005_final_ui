"""pipeline.run_codegen — Phase-D CLI: node/4 terms -> generated target code.

Reads every out/ir/<lang>/*.node4.json and writes one generated file per IR
file, generated ONLY from the node/4 terms (codegen law) via the
per-language mapping module. This file holds neither term-shape nor layout
knowledge of its own — it resolves <lang> to a generator module, asks that
module where its output belongs (see default_out_dir), and drives it over
every IR file, same shape as pipeline.run_fold's language-blind CLI.

Registered languages, and what each one generates:
    pig    pipeline.codegen.pig_pyspark    -> out/pyspark/pig/<stem>.py
    hive   pipeline.codegen.hive_pyspark   -> out/pyspark/hive/<stem>.py
    sqoop  pipeline.codegen.sqoop_python   -> out/wrappers/<stem>.py
             (Python wrapper STUBS, not runnable PySpark — a Sqoop command
              moves data between an external DB and HDFS/Hive, which no
              local PySpark session can stand in for)
    oozie  pipeline.codegen.oozie_airflow  -> out/airflow/dags/<stem>.py
             (Airflow DAG files, so the output dir is a `dags_folder`)

CLI:
    python3 -m pipeline.run_codegen <lang>
        [--ir-dir out/ir/<lang>]  (default derived from <lang>)
        [--out-dir DIR]           (default asked of the generator module,
                                    see default_out_dir; passed through to
                                    the generator per file)
        [--file STEM]             (generate only <STEM>.node4.json)

Prints one line per generated file and exits 0 only if every file in
--ir-dir generated without error, its blocks all carry "# blockid: b_00N"
headers, and the generated source parses as valid Python (ast.parse).
"""
import argparse
import ast
import importlib
import sys
from pathlib import Path

_GENERATOR_MODULES = {
    "pig": "pipeline.codegen.pig_pyspark",
    "hive": "pipeline.codegen.hive_pyspark",
    "sqoop": "pipeline.codegen.sqoop_python",
    "oozie": "pipeline.codegen.oozie_airflow",
}

def default_out_dir(lang):
    """Where <lang>'s generated files go, ASKED OF the generator module
    rather than tabulated here: a generator that writes somewhere other
    than the common out/pyspark/<lang> declares its own repo-relative
    DEFAULT_OUT_DIR (pipeline.codegen.sqoop_python -> out/wrappers, since
    wrapper STUBS are not PySpark programs; pipeline.codegen.oozie_airflow
    -> out/airflow/dags, an Airflow `dags_folder`). Keeping the answer in
    the one module that already needs it means this runner holds no
    per-language layout knowledge of its own, and there is exactly one
    place a lane's layout law can be read or changed. Generators that use
    the common layout (pig, hive) simply declare nothing and fall through.
    """
    return getattr(load_generator(lang), "DEFAULT_OUT_DIR", None) or (Path("out/pyspark") / lang)


def load_generator(lang):
    module_path = _GENERATOR_MODULES.get(lang)
    if module_path is None:
        raise ValueError(f"run_codegen: no generator module registered for lang {lang!r}")
    return importlib.import_module(module_path)


def verify_generated(py_path):
    """Every block starts with '# blockid: b_00N', and the file parses as
    valid Python. Returns a list of problem strings (empty == OK)."""
    problems = []
    text = Path(py_path).read_text(encoding="utf-8")
    try:
        ast.parse(text, filename=str(py_path))
    except SyntaxError as e:
        problems.append(f"generated file does not parse as Python: {e}")

    blockid_lines = [ln for ln in text.splitlines() if ln.startswith("# blockid: ")]
    if not blockid_lines:
        problems.append("no '# blockid: b_00N' headers found")
    for ln in blockid_lines:
        rest = ln[len("# blockid: "):].strip()
        if not (rest.startswith("b_") and rest[2:].isdigit()):
            problems.append(f"malformed blockid header: {ln!r}")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m pipeline.run_codegen")
    ap.add_argument("lang")
    ap.add_argument("--ir-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--file", default=None, help="generate only this stem's *.node4.json")
    args = ap.parse_args(argv)

    lang = args.lang

    # Resolve the generator FIRST: an unregistered <lang> has to come back as
    # the "no generator module registered" message and exit 1, and since
    # default_out_dir now asks the generator module where its output goes,
    # that lookup has to already have been reported on by here.
    try:
        gen = load_generator(lang)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    ir_dir = Path(args.ir_dir) if args.ir_dir else Path("out/ir") / lang
    out_dir = Path(args.out_dir) if args.out_dir else default_out_dir(lang)

    if not ir_dir.is_dir():
        print(f"ERROR: IR dir not found: {ir_dir}", file=sys.stderr)
        return 1

    files = sorted(ir_dir.glob("*.node4.json"))
    if args.file:
        files = [f for f in files if f.name == f"{args.file}.node4.json"]
    if not files:
        print(f"ERROR: no *.node4.json files found in {ir_dir}", file=sys.stderr)
        return 1

    all_ok = True
    rows = []
    for ir_path in files:
        stem = ir_path.name[: -len(".node4.json")]
        out_path = out_dir / f"{stem}.py"
        try:
            gen.generate_file(ir_path, out_py_path=out_path, lang=lang)
            problems = verify_generated(out_path)
            ok = not problems
        except Exception as e:
            problems = [f"generation raised: {e}"]
            ok = False
        all_ok = all_ok and ok
        rows.append((stem, out_path, ok, problems))

    name_w = max(len(r[0]) for r in rows)
    for stem, out_path, ok, problems in rows:
        verdict = "OK" if ok else "FAIL"
        print(f"{stem.ljust(name_w)}  {verdict}  -> {out_path}")
        for p in problems:
            print(f"    {p}")

    print()
    print(f"ALL GENERATED: {'true' if all_ok else 'false'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
