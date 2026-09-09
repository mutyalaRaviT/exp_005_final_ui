"""pipeline.run_hive_docker -- Phase-D Hive reference lane on REAL Hive.

Why this file exists alongside run_reference_hive.py
----------------------------------------------------
`run_reference_hive.py` runs the corpus .hql through DuckDB, because
there was no Hive here to run it on. That is a good fast lane, but it is
not Hive: DuckDB agrees with Hive on the easy cases and is free to
disagree on the interesting ones. This module runs the same .hql files
through an actual Apache Hive 4.0.1 HiveServer2 in a container, so the
two can be compared. A disagreement between them is not a bug in this
file -- it is the finding this lane exists to produce.

The one real translation this lane has to do
--------------------------------------------
Hive's `LOCATION` must be a DIRECTORY. The corpus writes
`LOCATION 'corpus/data/hive/orders.csv'` -- a path to a FILE -- which
DuckDB's `read_csv` accepts and Hive does not. So each input named in the
manifest is staged into its own directory before the run:

    corpus/data/hive/orders.csv
      -> out/hive_stage/<stem>/orders/orders.csv     (on the host)
      -> /data/<stem>/orders                         (as Hive sees it)

and the LOCATION in the statement is rewritten to that directory. This
is done per manifest input, by name, never per corpus file -- the same
no-per-file-special-case rule the DuckDB lane follows.

Isolation
---------
Each .hql runs in its own Hive database (`hql_<stem>`), created before
and dropped after. The embedded Derby metastore is shared across runs, so
without this the second file's `CREATE EXTERNAL TABLE orders` would
collide with the first file's.

Outputs
-------
For every manifest output, `out/hive_real/<stem>/<name>.csv`, headerless
and comma-separated -- the same layout law as the DuckDB lane, so
DataMatch can read either without knowing which produced it.

CLI:
    python3 -m pipeline.run_hive_docker
        [--corpus-dir corpus/hive/small]
        [--stem STEM]        (run only this one .hql)
        [--keep-db]          (leave the Hive database behind, for debugging)
        [--compare]          (also diff against out/hive_ref, the DuckDB lane)

Exits 0 only if every file ran and every manifest output was written.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from pipeline.hive_client import HiveClient, HiveError

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGE_ROOT = REPO_ROOT / "out" / "hive_stage"
RESULT_ROOT = REPO_ROOT / "out" / "hive_real"

# Where the two bind mounts appear inside the containers. Kept next to
# each other so the compose file and this module can be checked against
# one another at a glance.
CONTAINER_DATA = "/data"
CONTAINER_RESULTS = "/results"

_LOCATION_RE = re.compile(r"LOCATION\s+'([^']*)'", re.IGNORECASE)


def stage_inputs(manifest, stem):
    """Copy each manifest input into its own directory under out/hive_stage.

    Returns {host csv path (as written in the .hql) -> container directory}.
    Keyed by the path string the statement actually contains, so the
    rewrite below is a straight lookup rather than a second guess at
    which table a LOCATION belongs to.
    """
    mapping = {}
    for inp in manifest.get("inputs", []):
        src = REPO_ROOT / inp["path"]
        if not src.is_file():
            raise FileNotFoundError(f"corpus input not found: {src}")
        table_dir = STAGE_ROOT / stem / inp["name"]
        # Rebuilt every run: a stale file left in the directory would be
        # silently unioned into the table by Hive, which reads the whole
        # directory rather than one named file.
        if table_dir.exists():
            shutil.rmtree(table_dir)
        table_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, table_dir / src.name)
        mapping[inp["path"]] = f"{CONTAINER_DATA}/{stem}/{inp['name']}"
    return mapping


def rewrite_locations(hql_text, mapping):
    """Point every LOCATION at its staged directory.

    A LOCATION whose path is not in the manifest is left untouched and
    reported by the caller: silently rewriting an unknown path would let
    a typo in the corpus read the wrong data and still look green.
    """
    unmapped = []

    def sub(m):
        original = m.group(1)
        if original in mapping:
            return f"LOCATION '{mapping[original]}'"
        unmapped.append(original)
        return m.group(0)

    return _LOCATION_RE.sub(sub, hql_text), unmapped


def run_one(hql_path, manifest_path, hive, keep_db=False):
    """Stage, rewrite, run and export one corpus file. Returns a report dict."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stem = Path(manifest.get("file", str(hql_path))).stem
    database = f"hql_{stem}"

    mapping = stage_inputs(manifest, stem)
    hql_text, unmapped = rewrite_locations(
        hql_path.read_text(encoding="utf-8"), mapping)
    if unmapped:
        raise HiveError(
            f"LOCATION path(s) not present in the manifest inputs: {unmapped}. "
            f"Add them to {manifest_path.name} or fix the .hql."
        )

    # DROP first: a previous crashed run may have left the database
    # behind, and CREATE DATABASE would then fail for a reason that has
    # nothing to do with the file under test.
    hive.sql(f"DROP DATABASE IF EXISTS {database} CASCADE")
    hive.sql(f"CREATE DATABASE {database}")

    try:
        report = hive.script(hql_text, database=database)
        if not report.get("ok"):
            failed = [r for r in report.get("results", []) if not r["ok"]]
            first = failed[0] if failed else {}
            raise HiveError(
                f"statement {first.get('index')} failed: {first.get('error')}\n"
                f"  statement was: {first.get('statement')}"
            )

        out_dir = RESULT_ROOT / stem
        out_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for out in manifest.get("outputs", []):
            name = out["name"]
            hive.export_csv(
                table=name,
                container_path=f"{CONTAINER_RESULTS}/{stem}/{name}.csv",
                database=database,
            )
            written.append(str(out_dir / f"{name}.csv"))
        return {"stem": stem, "outputs": written,
                "statements": report.get("statement_count", 0)}
    finally:
        if not keep_db:
            try:
                hive.sql(f"DROP DATABASE IF EXISTS {database} CASCADE")
            except HiveError:
                # Never let cleanup mask the real error from the run.
                pass


def compare_with_duckdb(stem, outputs):
    """Diff this lane's CSVs against the DuckDB lane's, if it has run.

    Row-set comparison, not byte comparison: the two engines are free to
    format a double differently, and ORDER BY ties can land either way.
    Reported, never fatal -- a disagreement is a finding for a human to
    read, not a reason for this script to fail.
    """
    notes = []
    for path in outputs:
        real = Path(path)
        ref = REPO_ROOT / "out" / "hive_ref" / stem / real.name
        if not ref.is_file():
            notes.append(f"{real.name}: no DuckDB lane output to compare (run run_reference_hive)")
            continue
        real_rows = sorted(real.read_text(encoding="utf-8").splitlines())
        ref_rows = sorted(ref.read_text(encoding="utf-8").splitlines())
        if real_rows == ref_rows:
            notes.append(f"{real.name}: MATCH ({len(real_rows)} rows)")
        else:
            notes.append(
                f"{real.name}: DIFFER (hive {len(real_rows)} rows, duckdb {len(ref_rows)} rows)")
    return notes


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m pipeline.run_hive_docker")
    ap.add_argument("--corpus-dir", default="corpus/hive/small")
    ap.add_argument("--stem", default=None, help="run only this one .hql file's stem")
    ap.add_argument("--keep-db", action="store_true",
                    help="leave the per-file Hive database behind for debugging")
    ap.add_argument("--compare", action="store_true",
                    help="also diff each output against the DuckDB lane in out/hive_ref")
    args = ap.parse_args(argv)

    corpus_dir = REPO_ROOT / args.corpus_dir
    if not corpus_dir.is_dir():
        print(f"ERROR: corpus dir not found: {corpus_dir}", file=sys.stderr)
        return 1

    hql_files = sorted(corpus_dir.glob("*.hql"))
    if args.stem:
        hql_files = [f for f in hql_files if f.stem == args.stem]
    if not hql_files:
        print(f"ERROR: no *.hql files found in {corpus_dir}", file=sys.stderr)
        return 1

    hive = HiveClient()
    try:
        hive.ensure_up()
    except HiveError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    rows = []
    all_ok = True
    for hql_path in hql_files:
        manifest_path = Path(str(hql_path) + ".io.json")
        if not manifest_path.is_file():
            rows.append((hql_path.stem, False, [], f"missing manifest {manifest_path}", []))
            all_ok = False
            continue
        try:
            result = run_one(hql_path, manifest_path, hive, keep_db=args.keep_db)
            notes = compare_with_duckdb(result["stem"], result["outputs"]) if args.compare else []
            rows.append((result["stem"], True, result["outputs"], None, notes))
        except Exception as e:
            rows.append((hql_path.stem, False, [], f"{type(e).__name__}: {e}", []))
            all_ok = False

    name_w = max((len(r[0]) for r in rows), default=4)
    for stem, ok, outputs, err, notes in rows:
        print(f"{stem.ljust(name_w)}  {'OK' if ok else 'FAIL'}")
        if ok:
            for o in outputs:
                print(f"    -> {o}")
            for n in notes:
                print(f"    vs duckdb: {n}")
        else:
            print(f"    ERROR: {err}")

    print()
    print(f"ALL REAL-HIVE RUNS OK: {'true' if all_ok else 'false'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
