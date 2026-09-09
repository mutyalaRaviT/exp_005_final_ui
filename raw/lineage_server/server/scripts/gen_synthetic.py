"""Deterministic synthetic lineage generator for the 3,000,000-edge perf test
(Task 15).

Fills `files` + `lineage` directly with set-based DuckDB SQL — no SAS text is
parsed — so 30,000 files x 100 edges/file generates in seconds instead of
however long the real engine would take to parse 30,000 files. The row
*shape* matches `sas_lineage.store.LineageStore`'s schema exactly (same
column names/types `Service.edges_arrow` reads), so the perf test exercises
the real DuckDB -> Arrow -> IPC serialize path on realistic data volume.

Deterministic: (files, edges_per_file, seed) always produces byte-identical
`files`/`lineage` tables, so perf numbers are reproducible run to run.

One edge in five is FILE_FLOW, the rest BLOCK_FLOW (deterministic by
`(fi + ei + seed) % 5`, not by anything a random draw could vary between
runs) so the generated data flows through the same `edge_type -> level /
provenance` mapping `Service._provided_edges` uses in production
(BLOCK_FLOW -> block/fact, everything else -> file/inferred).
"""
import argparse
import sys
from pathlib import Path

_EXP_2 = Path(__file__).resolve().parents[2] / "exp_2"
if str(_EXP_2) not in sys.path:
    sys.path.insert(0, str(_EXP_2))

from sas_lineage.store import LineageStore  # noqa: E402


def generate(db_path: str | Path, files: int, edges_per_file: int,
             seed: int = 42) -> dict:
    """Fill `files` (one row per synthetic file) and `lineage` (`files *
    edges_per_file` rows) in the DuckDB database at `db_path`. Any existing
    rows in those two tables are replaced first, so re-running with the same
    arguments is idempotent. Returns `{"files": n, "edges": n}`."""
    if files < 0 or edges_per_file < 0:
        raise ValueError("files and edges_per_file must be >= 0")
    store = LineageStore(db_path)
    con = store.con
    con.execute("DELETE FROM lineage")
    con.execute("DELETE FROM files")

    if files > 0:
        con.execute(
            """
            INSERT INTO files
            SELECT
                'proj/file_' || fi || '.sas'  AS fileid,
                'file_' || fi || '.sas'       AS sasfilename,
                'proj'                        AS folder_path,
                md5(fi::VARCHAR)              AS sashashcode,
                'pass'                        AS conversion_status,
                100                           AS loc,
                TIMESTAMP '2026-01-01 00:00:00' AS analyzed_at
            FROM generate_series(0, ?) AS t(fi)
            """,
            [files - 1],
        )

    if files > 0 and edges_per_file > 0:
        con.execute(
            """
            INSERT INTO lineage
            SELECT
                'proj/file_' || fi || '.sas' AS fileid,
                'b_' || ei || '_'
                    || substr(md5(fi::VARCHAR || '.' || ei::VARCHAR), 1, 8)
                    AS block_id,
                'b_' || ei || '_'
                    || substr(md5(fi::VARCHAR || '.' || ei::VARCHAR), 1, 8)
                    || ':t_1_work.src_' || fi || '_' || ei AS source_ref_id,
                'b_' || ei || '_'
                    || substr(md5(fi::VARCHAR || '.' || ei::VARCHAR), 1, 8)
                    || ':t_2_work.dst_' || fi || '_' || ei AS target_ref_id,
                'work.src_' || fi || '_' || ei AS source_canonical_name,
                'work.dst_' || fi || '_' || ei AS target_canonical_name,
                'work' AS source_db_schema,
                'work' AS target_db_schema,
                ''     AS source_lib_path,
                ''     AS target_ref_path,
                'work' AS dst_source_db_schema,
                'work' AS dst_target_db_schema,
                'Y'    AS log_verified,
                CASE WHEN (fi + ei + ?) % 5 = 0 THEN 'FILE_FLOW'
                     ELSE 'BLOCK_FLOW' END AS edge_type,
                'proj' AS folder_path,
                'green' AS freshness
            FROM generate_series(0, ?) AS f(fi),
                 generate_series(0, ?) AS e(ei)
            """,
            [seed, files - 1, edges_per_file - 1],
        )

    counts = {
        "files": con.execute("SELECT count(*) FROM files").fetchone()[0],
        "edges": con.execute("SELECT count(*) FROM lineage").fetchone()[0],
    }
    store.close()
    return counts


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=int, default=30_000,
                        help="number of synthetic files (default 30000)")
    parser.add_argument("--edges-per-file", type=int, default=100,
                        help="synthetic lineage rows per file (default 100)")
    parser.add_argument("--db", type=Path, required=True,
                        help="DuckDB file to fill (created if missing)")
    parser.add_argument("--seed", type=int, default=42,
                        help="deterministic seed for the edge_type mix")
    args = parser.parse_args(argv)
    counts = generate(args.db, args.files, args.edges_per_file, args.seed)
    print(f"files={counts['files']} edges={counts['edges']} -> {args.db}")


if __name__ == "__main__":
    main()
