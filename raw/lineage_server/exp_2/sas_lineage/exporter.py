"""Excel export of the lineage graph — one row per edge.

Columns (fixed schema, in this order):
  fileid, block_id, source_ref_id, target_ref_id,
  source_canonical_name, target_canonical_name,
  source_db_schema, target_db_schema,
  source_lib_path, target_ref_path,
  dst_source_db_schema, dst_target_db_schema,
  log_verified (always empty for now)

Notes:
  fileid            = the file's path relative to the analysis root, with
                      "/" separators ("ankitha_1/12_txn_agg.sas") — STABLE
                      across edits; the content hash lives in the store's
                      `sashashcode` column and only flags "this changed"
  *_ref_id          = occurrence id (b_2:t_1); block_id is the target side's block
  *_db_schema       = SAS libref (part before the dot; unqualified -> "work")
  source_lib_path / target_ref_path = physical path from a `libname` statement,
                      empty when the libref has no libname in the file
  dst_*             = destination-system schemas, filled from an optional
                      schema_map; empty by default
  log_verified      = always empty for now

Usage:
  python -m sas_lineage.exporter out.xlsx file1.sas file2.sas ...
"""
import sys
from pathlib import Path

from openpyxl import Workbook

from sas_lineage.pipeline import Analysis, analyze_file

COLUMNS = [
    "fileid", "block_id", "source_ref_id", "target_ref_id",
    "source_canonical_name", "target_canonical_name",
    "source_db_schema", "target_db_schema",
    "source_lib_path", "target_ref_path",
    "dst_source_db_schema", "dst_target_db_schema",
    "log_verified",
]

ISSUE_COLUMNS = ["fileid", "block_id", "status", "unresolved"]


def make_fileid(path: Path, base_dir: Path | None = None) -> str:
    """`<folder>/<name>` — the file's path relative to `base_dir`, always with
    `/` separators (Windows backslashes normalized).

    The id is STABLE: editing a file never changes it, so human notes and
    edits keyed on a fileid survive. "Did this file change?" is answered by
    the content hash stored beside it (`files.sashashcode`), never by the id.
    The folder component keeps two same-named files in different folders from
    colliding; with no `base_dir` the immediate parent folder is used."""
    path = Path(path)
    folder = relative_folder(path, base_dir).replace("\\", "/")
    return f"{folder}/{path.name}" if folder else path.name


def relative_folder(path: Path, base_dir: Path | None) -> str:
    """One shared folder rule for the store and the UI: the path's folder
    relative to base_dir; the base folder's own name at the top level; the
    plain parent for paths outside base_dir."""
    path = Path(path).resolve()
    if base_dir is None:
        return path.parent.name
    base_dir = Path(base_dir).resolve()
    try:
        relative = str(path.parent.relative_to(base_dir))
    except ValueError:
        return str(path.parent)
    return base_dir.name if relative == "." else relative


def schema_of(name: str) -> str:
    return name.split(".", 1)[0].lower() if "." in name else "work"


def edge_rows(analysis: Analysis, fileid: str,
              schema_map: dict[str, str] | None = None) -> list[dict]:
    """One row per edge (BLOCK_FLOW and FILE_FLOW), in edge order."""
    schema_map = schema_map or {}
    occurrence = {
        o.display: o
        for b in analysis.blocks
        for o in [*b.reads, *b.writes]
    }
    rows = []
    for edge in analysis.edges:
        src, dst = occurrence[edge.source], occurrence[edge.target]
        src_schema, dst_schema = schema_of(src.name), schema_of(dst.name)
        rows.append({
            "fileid": fileid,
            "block_id": dst.block_id,  # the block where the flow lands
            "source_ref_id": src.id,
            "target_ref_id": dst.id,
            "source_canonical_name": src.canonical,
            "target_canonical_name": dst.canonical,
            "source_db_schema": src_schema,
            "target_db_schema": dst_schema,
            "source_lib_path": analysis.libnames.get(src_schema, ""),
            "target_ref_path": analysis.libnames.get(dst_schema, ""),
            "dst_source_db_schema": schema_map.get(src_schema, ""),
            "dst_target_db_schema": schema_map.get(dst_schema, ""),
            "log_verified": "",  # always empty for now
            # not an Excel column (COLUMNS is fixed); consumed by the store
            "edge_type": edge.edge_type,
        })
    return rows


def issue_rows(analysis: Analysis, fileid: str) -> list[dict]:
    """Blocks that did not fully parse — kept visible, never dropped."""
    return [
        {
            "fileid": fileid,
            "block_id": b.block_id,
            "status": b.status,
            "unresolved": " | ".join(b.unresolved),
        }
        for b in analysis.blocks
        if b.status != "PARSED"
    ]


def export_excel(sas_paths: list[str | Path], out_path: str | Path,
                 schema_map: dict[str, str] | None = None,
                 registry_path: Path | None = None) -> Path:
    """Analyze every SAS file and write one workbook: sheet `lineage` (one
    row per edge) and sheet `issues` (non-PARSED blocks)."""
    workbook = Workbook()
    lineage = workbook.active
    lineage.title = "lineage"
    lineage.append(COLUMNS)
    issues = workbook.create_sheet("issues")
    issues.append(ISSUE_COLUMNS)

    for sas_path in sas_paths:
        sas_path = Path(sas_path)
        analysis = analyze_file(sas_path, registry_path=registry_path)
        fileid = make_fileid(sas_path)
        for row in edge_rows(analysis, fileid, schema_map=schema_map):
            lineage.append([row[c] for c in COLUMNS])
        for row in issue_rows(analysis, fileid):
            issues.append([row[c] for c in ISSUE_COLUMNS])

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(out_path)
    return out_path


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print("usage: python -m sas_lineage.exporter <out.xlsx> <file.sas> [...]",
              file=sys.stderr)
        return 64
    out = export_excel(argv[1:], argv[0])
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
