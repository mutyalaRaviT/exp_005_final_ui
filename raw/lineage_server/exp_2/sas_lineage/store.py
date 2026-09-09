"""DuckDB enrichment store for SAS lineage (built for ~30,000 files).

One database, several tables keyed by fileid / block_id:

    files        one row per SAS file (conversion_status, folder_path, ...)
    blocks       blockid -> sas code + parse status
    lineage      the Excel-equivalent rows (plus edge_type)
    macros       macro definitions found per file
    macro_calls  every macro invocation (call block id, definition block id)
    events       append-only log of every write (the recovery trail)

Storage layout around the database:

    parquet export   COPY ... PARTITION_BY folder_path  (partition pruning
                     over the SAS folder tree) + pivot parquets indexed by
                     table name / macro name / file
    sessions         each analysis session writes its own events parquet;
                     consolidate_sessions() replays them into a canonical db
    checkpoints      periodic copies of the .duckdb file (weekly cadence)
    recovery         latest checkpoint + replay of newer events = the dataset
                     (keep ~1 month of event parquets)

Every write goes through apply_bundle(); ingest additionally appends the
bundle to `events`, which is what makes replay possible.
"""
import json
import re
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

import duckdb

from sas_lineage.exporter import edge_rows, issue_rows, make_fileid, relative_folder
from sas_lineage.pipeline import analyze_file
from sas_lineage.registry import file_hash
from sas_lineage.ui_export import conversion_status

LINEAGE_COLUMNS = [
    "fileid", "block_id", "source_ref_id", "target_ref_id",
    "source_canonical_name", "target_canonical_name",
    "source_db_schema", "target_db_schema",
    "source_lib_path", "target_ref_path",
    "dst_source_db_schema", "dst_target_db_schema",
    "log_verified", "edge_type", "folder_path", "freshness",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    fileid VARCHAR PRIMARY KEY, sasfilename VARCHAR, folder_path VARCHAR,
    sashashcode VARCHAR, conversion_status VARCHAR, loc INTEGER,
    analyzed_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS blocks (
    fileid VARCHAR, block_id VARCHAR, status VARCHAR, kind VARCHAR,
    sas_code VARCHAR, folder_path VARCHAR, PRIMARY KEY (fileid, block_id));
CREATE TABLE IF NOT EXISTS lineage (
    fileid VARCHAR, block_id VARCHAR, source_ref_id VARCHAR,
    target_ref_id VARCHAR, source_canonical_name VARCHAR,
    target_canonical_name VARCHAR, source_db_schema VARCHAR,
    target_db_schema VARCHAR, source_lib_path VARCHAR,
    target_ref_path VARCHAR, dst_source_db_schema VARCHAR,
    dst_target_db_schema VARCHAR, log_verified VARCHAR,
    edge_type VARCHAR, folder_path VARCHAR);
CREATE TABLE IF NOT EXISTS macros (
    fileid VARCHAR, macroname VARCHAR, params VARCHAR, definition VARCHAR,
    PRIMARY KEY (fileid, macroname));
CREATE TABLE IF NOT EXISTS macro_calls (
    fileid VARCHAR, macroname VARCHAR, instance INTEGER,
    call_block_id VARCHAR, def_block_id VARCHAR, args VARCHAR);
CREATE TABLE IF NOT EXISTS sources (
    fileid VARCHAR PRIMARY KEY, folder_path VARCHAR,
    sashashcode VARCHAR, source VARCHAR);
CREATE TABLE IF NOT EXISTS sync_meta (key VARCHAR PRIMARY KEY, value VARCHAR);
ALTER TABLE lineage ADD COLUMN IF NOT EXISTS freshness VARCHAR DEFAULT 'green';
ALTER TABLE blocks ADD COLUMN IF NOT EXISTS kind VARCHAR;
CREATE TABLE IF NOT EXISTS lost_flows (
    fileid VARCHAR, block_id VARCHAR, src VARCHAR, dst VARCHAR,
    table_name VARCHAR, level VARCHAR, detected_at TIMESTAMP,
    PRIMARY KEY (fileid, src, dst, level));
CREATE TABLE IF NOT EXISTS events (
    seq BIGINT, ts TIMESTAMP, session_id VARCHAR, event_type VARCHAR,
    fileid VARCHAR, payload VARCHAR);
CREATE SEQUENCE IF NOT EXISTS event_seq START 1;
"""

_PER_FILE_TABLES = ["files", "blocks", "lineage", "macros", "macro_calls",
                     "sources"]


def build_bundle(path: str | Path, base_dir: str | Path | None = None) -> dict:
    """Analyze one SAS file into the store's write unit (a plain dict, so it
    can live in the event log and be replayed)."""
    path = Path(path)
    analysis = analyze_file(path, registry_path=None)
    source = path.read_text()
    folder = relative_folder(path, base_dir)  # same rule as the UI
    fileid = make_fileid(path, base_dir)      # stable path id, same base

    blocks = [
        {"fileid": fileid, "block_id": b.block_id, "status": b.status,
         "kind": b.kind,
         "sas_code": _block_source(source, b.block_id), "folder_path": folder}
        for b in analysis.blocks
    ]
    status = conversion_status([{"status": b.status} for b in analysis.blocks])
    rows = edge_rows(analysis, fileid)
    for row in rows:
        row["folder_path"] = folder
    return {
        "file": {
            "fileid": fileid, "sasfilename": path.name, "folder_path": folder,
            "sashashcode": file_hash(source), "conversion_status": status,
            "loc": sum(1 for line in source.splitlines() if line.strip()),
            "analyzed_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
        },
        "blocks": blocks,
        "lineage": rows,
        # the raw text rides the bundle so search never needs the disk (or
        # rg) in production, and replay rebuilds it byte-identical
        "sources": [{
            "fileid": fileid, "folder_path": folder,
            "sashashcode": file_hash(source), "source": source,
        }],
        "macros": [
            {"fileid": fileid, "macroname": m.name,
             "params": json.dumps(m.params), "definition": m.body}
            for m in analysis.macros.values()
        ],
        "macro_calls": [
            {"fileid": fileid, "macroname": c.name, "instance": c.instance,
             "call_block_id": c.call_block_id or "", "def_block_id": c.def_block_id,
             "args": json.dumps(c.args)}
            for c in analysis.macro_calls
        ],
        "issues": issue_rows(analysis, fileid),
    }


def _block_source(source: str, block_id: str) -> str:
    """Per-block code: the annotated span when the id is injected, otherwise
    empty (the full file is one read away via files.sasfilename)."""
    if ":" not in block_id or "#" in block_id:
        return ""  # fallback b_<n>_<hash8> id or a macro instance — no span
    raw_id = block_id.split(".")[0]
    m = re.search(
        r"/\*BLOCKID\s+" + re.escape(raw_id) + r"\b.*?\*/(.*?)/\*ENDBLOCKID",
        source, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


class LineageStore:
    """The DuckDB store. Use as a context manager or call close()."""

    def __init__(self, db_path: str | Path, session_id: str | None = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(self.db_path))
        self.session_id = session_id or uuid.uuid4().hex[:12]
        for statement in _SCHEMA.strip().split(";"):
            if statement.strip():
                self.con.execute(statement)

    # ---- writes -------------------------------------------------------------

    def ingest_file(self, path: str | Path, base_dir: str | Path | None = None) -> str:
        """Analyze + upsert one SAS file, and record the event. Returns fileid."""
        bundle = build_bundle(path, base_dir)
        self.apply_bundle(bundle)
        self._append_event("file_ingested", bundle["file"]["fileid"], bundle)
        return bundle["file"]["fileid"]

    def apply_bundle(self, bundle: dict):
        """Upsert a bundle (also used by event replay — no event is written).

        Freshness is computed here against the rows being replaced — not in
        `build_bundle` — so an old event payload replays to the same colors
        it produced live:

            green   block id (content hash) unchanged, or first-ever parse
            yellow  block changed, identical flow survived
            red     block changed AND the flow is a new extraction

        Flows the previous parse had that the new one lost become red ghost
        rows in `lost_flows` (cleared when the flow reappears)."""
        fileid = bundle["file"]["fileid"]
        prev_blocks = {r[0] for r in self.con.execute(
            "SELECT block_id FROM blocks WHERE fileid = ?",
            [fileid]).fetchall()}
        #: old flow -> the block it lived in, captured BEFORE the delete
        prev_block_of = {(r[0], r[1], r[2]): r[3] for r in self.con.execute(
            "SELECT source_canonical_name, target_canonical_name, edge_type, "
            "block_id FROM lineage WHERE fileid = ?", [fileid]).fetchall()}
        prev_flows = set(prev_block_of)

        new_flows = set()
        for row in bundle["lineage"]:
            key = (row["source_canonical_name"],
                   row["target_canonical_name"], row["edge_type"])
            new_flows.add(key)
            if not prev_blocks or row["block_id"] in prev_blocks:
                row["freshness"] = "green"
            elif key in prev_flows:
                row["freshness"] = "yellow"
            else:
                row["freshness"] = "red"

        for table in _PER_FILE_TABLES:
            self.con.execute(f"DELETE FROM {table} WHERE fileid = ?", [fileid])
        self._insert("files", [bundle["file"]])
        self._insert("blocks", bundle["blocks"])
        self._insert("lineage", bundle["lineage"], columns=LINEAGE_COLUMNS)
        self._insert("macros", bundle["macros"])
        self._insert("macro_calls", bundle["macro_calls"])
        # .get: bundles logged before the sources table existed still replay
        self._insert("sources", bundle.get("sources", []))
        self._update_lost_flows(fileid, prev_blocks, prev_block_of, new_flows)

    def _update_lost_flows(self, fileid, prev_blocks, prev_block_of,
                            new_flows):
        """Ghost bookkeeping: a flow the previous parse had and this one lost
        turns red; one that came back stops being a ghost."""
        for src, dst, _ in sorted(new_flows):
            self.con.execute(
                "DELETE FROM lost_flows WHERE fileid = ? AND src = ? "
                "AND dst = ?", [fileid, src, dst])
        if not prev_blocks:
            return
        for key in sorted(set(prev_block_of) - new_flows):
            src, dst, edge_type = key
            level = "block" if edge_type == "BLOCK_FLOW" else "file"
            self.con.execute(
                "INSERT OR REPLACE INTO lost_flows "
                "VALUES (?, ?, ?, ?, ?, ?, now())",
                [fileid, prev_block_of.get(key, ""), src, dst, src, level])

    def remove_file(self, fileid: str):
        """Delete every per-file row for a fileid gone from disk; logged so
        replay removes it too."""
        self._apply_removal(fileid)
        self._append_event("file_removed", fileid, {})

    def _apply_removal(self, fileid: str):
        for table in _PER_FILE_TABLES:
            self.con.execute(f"DELETE FROM {table} WHERE fileid = ?", [fileid])

    def enrich_file(self, fileid: str, **columns):
        """Update columns on `files` after a later pipeline step; logged."""
        allowed = {"conversion_status"}
        bad = set(columns) - allowed
        if bad:
            raise ValueError(f"not enrichable: {sorted(bad)}")
        for name, value in columns.items():
            self.con.execute(f"UPDATE files SET {name} = ? WHERE fileid = ?",
                             [value, fileid])
        self._append_event("file_enriched", fileid, columns)

    def _insert(self, table: str, rows: list[dict], columns: list[str] | None = None):
        if not rows:
            return
        columns = columns or list(rows[0].keys())
        placeholders = ", ".join("?" for _ in columns)
        self.con.executemany(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            [[row.get(c, "") for c in columns] for row in rows],
        )

    def _append_event(self, event_type: str, fileid: str, payload):
        # a persistent SEQUENCE, not max(seq)+1: pruning old event rows must
        # never reset the sequence, or recovery's seq filter replays stale data
        self.con.execute(
            "INSERT INTO events VALUES (nextval('event_seq'), now(), ?, ?, ?, ?)",
            [self.session_id, event_type, fileid, json.dumps(payload)],
        )

    # ---- parquet export -----------------------------------------------------

    def export_parquet(self, out_dir: str | Path):
        """Canonical parquet, partitioned by the SAS folder path."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for table in ["files", "blocks", "lineage"]:
            self.con.execute(
                f"COPY {table} TO '{out_dir / table}' "
                f"(FORMAT PARQUET, PARTITION_BY (folder_path), OVERWRITE_OR_IGNORE)")
        for table in ["macros", "macro_calls"]:
            self.con.execute(
                f"COPY {table} TO '{out_dir / (table + '.parquet')}' (FORMAT PARQUET)")

    def export_pivots(self, out_dir: str | Path):
        """Small index parquets: by table name, by macro name, by file."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        pivots = {
            "by_table": """
                WITH usage AS (
                    SELECT source_canonical_name AS table_name, fileid,
                           'read' AS role FROM lineage
                    UNION ALL
                    SELECT target_canonical_name, fileid, 'write' FROM lineage)
                SELECT table_name,
                       count(DISTINCT fileid) FILTER (role = 'read')  AS reader_files,
                       count(DISTINCT fileid) FILTER (role = 'write') AS writer_files,
                       list(DISTINCT fileid) AS files
                FROM usage GROUP BY table_name ORDER BY table_name""",
            "by_macro": """
                SELECT m.macroname,
                       list(DISTINCT m.fileid) AS defined_in,
                       coalesce(c.calls, 0) AS calls,
                       coalesce(c.calling_files, []) AS calling_files
                FROM macros m
                LEFT JOIN (SELECT macroname, count(*) AS calls,
                                  list(DISTINCT fileid) AS calling_files
                           FROM macro_calls GROUP BY macroname) c USING (macroname)
                GROUP BY m.macroname, c.calls, c.calling_files
                ORDER BY m.macroname""",
            "by_file": """
                SELECT f.fileid, f.sasfilename, f.folder_path, f.conversion_status,
                       f.loc, count(DISTINCT b.block_id) AS blocks,
                       count(l.fileid) AS edges
                FROM files f
                LEFT JOIN blocks b USING (fileid)
                LEFT JOIN lineage l USING (fileid)
                GROUP BY ALL ORDER BY f.folder_path, f.sasfilename""",
        }
        for name, query in pivots.items():
            self.con.execute(
                f"COPY ({query}) TO '{out_dir / (name + '.parquet')}' (FORMAT PARQUET)")

    # ---- sessions -----------------------------------------------------------

    def export_session_events(self, sessions_dir: str | Path) -> Path:
        """This session's events as one parquet under sessions/<session_id>/."""
        session_dir = Path(sessions_dir) / self.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        out = session_dir / "events.parquet"
        self.con.execute(
            f"COPY (SELECT * FROM events WHERE session_id = '{self.session_id}') "
            f"TO '{out}' (FORMAT PARQUET)")
        return out

    def consolidate_sessions(self, sessions_dir: str | Path) -> int:
        """Replay every session's events parquet into this store (ts order).
        Returns the number of events applied."""
        pattern = str(Path(sessions_dir) / "*" / "events.parquet")
        rows = self.con.execute(
            f"SELECT event_type, fileid, payload FROM read_parquet('{pattern}') "
            f"ORDER BY ts, seq").fetchall()
        applied = 0
        for event_type, fileid, payload in rows:
            self._replay(event_type, fileid, json.loads(payload))
            applied += 1
        return applied

    def _replay(self, event_type: str, fileid: str, payload):
        if event_type == "file_ingested":
            self.apply_bundle(payload)
        elif event_type == "file_removed":
            self._apply_removal(fileid)
        elif event_type == "file_enriched":
            for name, value in payload.items():
                self.con.execute(
                    f"UPDATE files SET {name} = ? WHERE fileid = ?", [value, fileid])

    # ---- checkpoints & recovery --------------------------------------------

    def checkpoint(self, checkpoints_dir: str | Path) -> Path:
        """Copy the database file (weekly cadence recommended)."""
        checkpoints_dir = Path(checkpoints_dir)
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.con.execute("CHECKPOINT")
        out = checkpoints_dir / f"lineage_{datetime.now():%Y%m%d_%H%M%S}.duckdb"
        shutil.copy2(self.db_path, out)
        return out

    def export_events_parquet(self, events_dir: str | Path) -> Path:
        events_dir = Path(events_dir)
        events_dir.mkdir(parents=True, exist_ok=True)
        out = events_dir / f"events_{datetime.now():%Y%m%d_%H%M%S_%f}.parquet"
        self.con.execute(f"COPY events TO '{out}' (FORMAT PARQUET)")
        return out

    def prune_events(self, days: int = 31) -> int:
        """Drop event rows older than `days` (they live on in the events
        parquets; keep ~1 month in the db)."""
        n = self.con.execute(
            "SELECT count(*) FROM events WHERE ts < now() - ? * INTERVAL 1 DAY",
            [days]).fetchone()[0]
        self.con.execute(
            "DELETE FROM events WHERE ts < now() - ? * INTERVAL 1 DAY", [days])
        return n

    def close(self):
        self.con.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def prune_checkpoints(checkpoints_dir: str | Path, keep_days: int = 35) -> list[Path]:
    """Delete checkpoints older than keep_days, always keeping the newest."""
    files = sorted(Path(checkpoints_dir).glob("lineage_*.duckdb"))
    removed = []
    cutoff = time.time() - keep_days * 86400
    for f in files[:-1]:  # never remove the newest
        if f.stat().st_mtime < cutoff:
            f.unlink()
            removed.append(f)
    return removed


def recover(checkpoint_file: str | Path, events_dir: str | Path,
            db_path: str | Path) -> "LineageStore":
    """Rebuild the dataset: restore the checkpoint, then replay any events in
    the events parquets newer than the checkpoint's last event."""
    shutil.copy2(checkpoint_file, db_path)
    store = LineageStore(db_path)
    last = store.con.execute("SELECT coalesce(max(seq), 0) FROM events").fetchone()[0]
    pattern = str(Path(events_dir) / "events_*.parquet")
    try:
        rows = store.con.execute(
            f"SELECT seq, event_type, fileid, payload FROM read_parquet('{pattern}') "
            f"WHERE seq > {last} ORDER BY seq").fetchall()
    except duckdb.IOException:
        rows = []
    for seq, event_type, fileid, payload in rows:
        store._replay(event_type, fileid, json.loads(payload))
        store.con.execute(
            "INSERT INTO events VALUES (?, now(), 'recovered', ?, ?, ?)",
            [seq, event_type, fileid, payload])
    # future appends must start beyond everything just replayed
    top = store.con.execute("SELECT coalesce(max(seq), 0) FROM events").fetchone()[0]
    store.con.execute("DROP SEQUENCE event_seq")
    store.con.execute(f"CREATE SEQUENCE event_seq START {top + 1}")
    return store
