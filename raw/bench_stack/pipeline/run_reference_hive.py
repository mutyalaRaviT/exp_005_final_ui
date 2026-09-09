"""pipeline.run_reference_hive — Phase-D Hive REFERENCE executor (DuckDB).

Why this file exists: DataMatch needs a ground truth to compare generated
PySpark against. For Pig that ground truth is `pig -x local`'s own
output (out/pig/<stem>/<name>/part-*, already on disk). Hive has no local
`hive -x local` here, so the reference side runs each corpus .hql through
DuckDB instead — chosen because the Hive SQL subset this corpus uses
(SELECT, CASE WHEN, COALESCE, CAST, JOIN..ON, WHERE/GROUP BY/HAVING/
ORDER BY/LIMIT, UNION ALL, subqueries) is already close enough to
standard SQL that DuckDB runs almost all of it completely unchanged.

This is the REFERENCE side, not the product pipeline (the Phase-D
contract explicitly allows this file to be regex/string-level), but it
still obeys one hard rule: no per-file special case. Every .hql
statement is classified by its own shape, never by which corpus file it
came from:

  - `CREATE EXTERNAL TABLE name (cols) ROW FORMAT ... LOCATION 'path'
    TBLPROPERTIES (...)` is rewritten to
    `CREATE VIEW name AS SELECT * FROM read_csv('path', header=<bool>,
    columns={...})` — the column list and the header flag (from
    skip.header.line.count) are both read straight out of the statement
    text, not out of a manifest or a per-file table.
  - Every other statement (CREATE TABLE ... AS SELECT, plain CREATE
    TABLE (cols), INSERT INTO ... SELECT) is standard SQL DuckDB already
    understands, so it runs as-is — the only mechanical edit applied
    uniformly is `STRING` -> `VARCHAR` (DuckDB's name for that type),
    since Hive's `STRING` keyword only ever appears in a type position
    in this corpus.

For every manifest output name, `COPY (SELECT * FROM <name>) TO
'out/hive_ref/<stem>/<name>.csv' (HEADER false, DELIMITER ',')` writes
the DataMatch-law-compatible reference file (layout law: one CSV per
output, headerless, comma-separated).

CLI:
    python3 -m pipeline.run_reference_hive
        [--corpus-dir corpus/hive/small]
        [--out-root out/hive_ref]
        [--stem STEM]           (run only this one .hql file)

Prints one line per file and exits 0 only if every file's statements ran
and every manifest output got written.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]

_DUCKDB_TYPE = {
    "int": "INTEGER",
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "long": "BIGINT",
    "double": "DOUBLE",
    "float": "FLOAT",
    "string": "VARCHAR",
    "varchar": "VARCHAR",
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
}

_CREATE_EXTERNAL_RE = re.compile(
    r"CREATE\s+EXTERNAL\s+TABLE\s+(\w+)\s*\((.*?)\)\s*"
    r"ROW\s+FORMAT\s+DELIMITED\s+FIELDS\s+TERMINATED\s+BY\s+'([^']*)'\s*"
    r"LOCATION\s+'([^']*)'"
    r"(?:\s*TBLPROPERTIES\s*\((?P<props>.*?)\))?\s*\Z",
    re.IGNORECASE | re.DOTALL,
)
_SKIP_HEADER_RE = re.compile(r"skip\.header\.line\.count'\s*=\s*'(\d+)'", re.IGNORECASE)
_STRING_KEYWORD_RE = re.compile(r"\bSTRING\b", re.IGNORECASE)


def _duckdb_type(hive_type):
    t = hive_type.lower()
    if t not in _DUCKDB_TYPE:
        raise ValueError(f"run_reference_hive: no DuckDB type mapped for Hive type {hive_type!r}")
    return _DUCKDB_TYPE[t]


def _parse_fields(col_block):
    """'order_id INT, customer_id INT, ...' -> [('order_id','INT'), ...].
    Every field in this corpus is a bare `name TYPE` pair (no nested
    parens, no per-column comments), so a plain top-level comma split is
    safe."""
    fields = []
    for chunk in col_block.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.match(r"(\w+)\s+(\w+)", chunk)
        if not m:
            raise ValueError(f"run_reference_hive: cannot parse column def {chunk!r}")
        fields.append((m.group(1), m.group(2)))
    return fields


def strip_comments(text):
    """Drop everything from '--' to end of line — Hive's only comment
    form in this corpus."""
    lines = []
    for line in text.splitlines():
        idx = line.find("--")
        if idx != -1:
            line = line[:idx]
        lines.append(line)
    return "\n".join(lines)


def split_statements(text):
    """Comment-stripped text -> a list of non-empty ';'-terminated
    statement bodies (the ';' itself dropped). None of this corpus's
    string literals contain a semicolon, so a plain split is safe."""
    text = strip_comments(text)
    return [p.strip() for p in text.split(";") if p.strip()]


def translate_create_external(stmt):
    """CREATE EXTERNAL TABLE ... ROW FORMAT ... LOCATION ... [TBLPROPERTIES
    (...)] -> a DuckDB `CREATE VIEW ... AS SELECT * FROM read_csv(...)`,
    with the column list and the header flag read straight out of the
    statement text (never out of a manifest — this mapping only needs
    the .hql statement itself)."""
    m = _CREATE_EXTERNAL_RE.search(stmt)
    if not m:
        raise ValueError(
            f"run_reference_hive: cannot parse CREATE EXTERNAL TABLE statement: {stmt[:160]!r}"
        )
    table_name = m.group(1)
    fields = _parse_fields(m.group(2))
    location = m.group(4)
    props_text = m.group("props") or ""
    hm = _SKIP_HEADER_RE.search(props_text)
    header = "true" if (hm and int(hm.group(1)) > 0) else "false"
    cols = ", ".join(f"'{name}': '{_duckdb_type(t)}'" for name, t in fields)
    return (
        f"CREATE VIEW {table_name} AS "
        f"SELECT * FROM read_csv('{location}', header={header}, columns={{{cols}}})"
    )


def translate_statement(stmt):
    """One .hql statement body -> one DuckDB-runnable statement. Only two
    rules, applied by the statement's own shape, never by filename:
      1. CREATE EXTERNAL TABLE -> translate_create_external.
      2. Everything else -> passed through, with the STRING type keyword
         swapped for DuckDB's VARCHAR (a no-op on statements that don't
         contain it)."""
    if re.match(r"\s*CREATE\s+EXTERNAL\s+TABLE\b", stmt, re.IGNORECASE):
        return translate_create_external(stmt)
    return _STRING_KEYWORD_RE.sub("VARCHAR", stmt)


def run_reference_for_file(hql_path, manifest_path, out_root, con):
    """Run every statement of one .hql file against `con` (expected to be
    a fresh, empty DuckDB connection — table/view names are not
    namespaced per file), then COPY every manifest output to
    out/hive_ref/<stem>/<name>.csv. Returns a dict with the statements
    run and the files written, for the CLI's own reporting."""
    hql_text = Path(hql_path).read_text(encoding="utf-8")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    stem = Path(manifest.get("file", hql_path)).stem

    executed = []
    for stmt in split_statements(hql_text):
        duck_sql = translate_statement(stmt)
        con.execute(duck_sql)
        executed.append(duck_sql)

    out_dir = Path(out_root) / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for out in manifest.get("outputs", []):
        name = out["name"]
        csv_path = out_dir / f"{name}.csv"
        con.execute(
            f"COPY (SELECT * FROM {name}) TO '{csv_path.as_posix()}' (HEADER false, DELIMITER ',')"
        )
        written.append(str(csv_path))

    return {"stem": stem, "statements": executed, "outputs": written}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m pipeline.run_reference_hive")
    ap.add_argument("--corpus-dir", default="corpus/hive/small")
    ap.add_argument("--out-root", default="out/hive_ref")
    ap.add_argument("--stem", default=None, help="run only this one .hql file's stem")
    args = ap.parse_args(argv)

    corpus_dir = Path(args.corpus_dir)
    if not corpus_dir.is_dir():
        print(f"ERROR: corpus dir not found: {corpus_dir}", file=sys.stderr)
        return 1

    hql_files = sorted(corpus_dir.glob("*.hql"))
    if args.stem:
        hql_files = [f for f in hql_files if f.stem == args.stem]
    if not hql_files:
        print(f"ERROR: no *.hql files found in {corpus_dir}", file=sys.stderr)
        return 1

    all_ok = True
    rows = []
    for hql_path in hql_files:
        manifest_path = Path(str(hql_path) + ".io.json")
        if not manifest_path.is_file():
            rows.append((hql_path.stem, False, [], f"missing manifest {manifest_path}"))
            all_ok = False
            continue
        con = duckdb.connect(database=":memory:")
        try:
            result = run_reference_for_file(hql_path, manifest_path, args.out_root, con)
            rows.append((hql_path.stem, True, result["outputs"], None))
        except Exception as e:
            rows.append((hql_path.stem, False, [], f"{type(e).__name__}: {e}"))
            all_ok = False
        finally:
            con.close()

    name_w = max((len(r[0]) for r in rows), default=4)
    for stem, ok, outputs, err in rows:
        verdict = "OK" if ok else "FAIL"
        print(f"{stem.ljust(name_w)}  {verdict}")
        if ok:
            for o in outputs:
                print(f"    -> {o}")
        else:
            print(f"    ERROR: {err}")

    print()
    print(f"ALL REFERENCE RUNS OK: {'true' if all_ok else 'false'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
