"""Integration tests: full example corpus through the DuckDB store —
partitioned parquet, pivots, sessions, checkpoints, event-log recovery."""
from pathlib import Path

from sas_lineage.store import LineageStore, prune_checkpoints, recover

EXAMPLES = Path(__file__).resolve().parent.parent.parent / "examples"


def ingest_all(store):
    for f in sorted(EXAMPLES.rglob("*.sas")):
        store.ingest_file(f, base_dir=EXAMPLES)


def test_parquet_partitioned_by_folder(tmp_path):
    with LineageStore(tmp_path / "db.duckdb") as store:
        ingest_all(store)
        store.export_parquet(tmp_path / "parquet")
    partitions = {p.name for p in (tmp_path / "parquet" / "lineage").iterdir()}
    assert {"folder_path=examples", "folder_path=landing",
            "folder_path=staging", "folder_path=mart"} <= partitions


def test_pivots(tmp_path):
    with LineageStore(tmp_path / "db.duckdb") as store:
        ingest_all(store)
        store.export_pivots(tmp_path / "pivots")
        row = store.con.execute(
            f"SELECT reader_files, writer_files FROM "
            f"read_parquet('{tmp_path}/pivots/by_table.parquet') "
            f"WHERE table_name = 'work.customers'").fetchone()
        assert row == (3, 1)  # ex2, ex3, build_summary read; load_customers writes
        macro = store.con.execute(
            f"SELECT calls FROM read_parquet('{tmp_path}/pivots/by_macro.parquet') "
            f"WHERE macroname = 'stage_table'").fetchone()
        assert macro == (2,)  # called twice in ex11
        files = store.con.execute(
            f"SELECT count(*) FROM read_parquet('{tmp_path}/pivots/by_file.parquet')"
        ).fetchone()[0]
        assert files == len(list(EXAMPLES.rglob("*.sas")))


def test_session_consolidation(tmp_path):
    sessions = tmp_path / "sessions"
    files = sorted(EXAMPLES.rglob("*.sas"))
    half = len(files) // 2

    with LineageStore(tmp_path / "s1.duckdb", session_id="sess1") as one:
        for f in files[:half]:
            one.ingest_file(f, base_dir=EXAMPLES)
        one.export_session_events(sessions)
    with LineageStore(tmp_path / "s2.duckdb", session_id="sess2") as two:
        for f in files[half:]:
            two.ingest_file(f, base_dir=EXAMPLES)
        two.export_session_events(sessions)

    with LineageStore(tmp_path / "canonical.duckdb") as canonical:
        applied = canonical.consolidate_sessions(sessions)
        assert applied == len(files)
        count = canonical.con.execute("SELECT count(*) FROM files").fetchone()[0]
        assert count == len(files)


def test_checkpoint_and_event_recovery(tmp_path):
    files = sorted(EXAMPLES.rglob("*.sas"))
    with LineageStore(tmp_path / "db.duckdb") as store:
        # checkpoint after the first few files...
        for f in files[:3]:
            store.ingest_file(f, base_dir=EXAMPLES)
        checkpoint = store.checkpoint(tmp_path / "checkpoints")
        # ...then more work happens, captured only in the event parquet
        for f in files[3:]:
            store.ingest_file(f, base_dir=EXAMPLES)
        store.export_events_parquet(tmp_path / "eventlog")
        expected = store.con.execute("SELECT count(*) FROM files").fetchone()[0]

    # disaster: the live db is gone — rebuild from checkpoint + event log
    (tmp_path / "db.duckdb").unlink()
    restored = recover(checkpoint, tmp_path / "eventlog", tmp_path / "db.duckdb")
    try:
        count = restored.con.execute("SELECT count(*) FROM files").fetchone()[0]
        assert count == expected == len(files)
    finally:
        restored.close()


def test_prune_checkpoints_keeps_newest(tmp_path):
    import os, time
    cp_dir = tmp_path / "checkpoints"
    cp_dir.mkdir()
    old = cp_dir / "lineage_20250101_000000.duckdb"
    new = cp_dir / "lineage_20260824_120000.duckdb"
    old.write_bytes(b"x")
    new.write_bytes(b"y")
    stale = time.time() - 90 * 86400
    os.utime(old, (stale, stale))
    removed = prune_checkpoints(cp_dir, keep_days=35)
    assert removed == [old]
    assert new.exists()


def test_prune_events(tmp_path):
    with LineageStore(tmp_path / "db.duckdb") as store:
        store.ingest_file(next(EXAMPLES.glob("ex1_*.sas")), base_dir=EXAMPLES)
        store.con.execute(
            "UPDATE events SET ts = now() - INTERVAL 60 DAY WHERE seq = 1")
        assert store.prune_events(days=31) == 1
        assert store.con.execute("SELECT count(*) FROM events").fetchone()[0] == 0


# ---- sources table (store-freshness plan, Task 1) ---------------------------

def test_ingest_writes_sources_row(tmp_path):
    sas = tmp_path / "a.sas"
    sas.write_text("data work.a; set work.x; run;")
    with LineageStore(tmp_path / "db.duckdb") as store:
        fileid = store.ingest_file(sas, tmp_path)
        row = store.con.execute(
            "SELECT fileid, sashashcode, source FROM sources "
            "WHERE fileid = ?", [fileid]).fetchone()
    assert row is not None
    assert row[2] == "data work.a; set work.x; run;"
    assert row[1]  # content hash present


def test_reingest_replaces_sources_row(tmp_path):
    sas = tmp_path / "a.sas"
    sas.write_text("data work.a; set work.x; run;")
    with LineageStore(tmp_path / "db.duckdb") as store:
        fileid = store.ingest_file(sas, tmp_path)
        sas.write_text("data work.b; set work.y; run;")
        store.ingest_file(sas, tmp_path)
        rows = store.con.execute(
            "SELECT source FROM sources WHERE fileid = ?", [fileid]).fetchall()
    assert rows == [("data work.b; set work.y; run;",)]


def test_replay_reproduces_sources(tmp_path):
    sas = tmp_path / "a.sas"
    sas.write_text("data work.a; set work.x; run;")
    sessions = tmp_path / "sessions"
    with LineageStore(tmp_path / "db1.duckdb") as store:
        store.ingest_file(sas, tmp_path)
        store.export_session_events(sessions)
    with LineageStore(tmp_path / "db2.duckdb") as fresh:
        fresh.consolidate_sessions(sessions)
        count = fresh.con.execute("SELECT count(*) FROM sources").fetchone()[0]
    assert count == 1


def test_replay_of_pre_sources_bundle_does_not_crash(tmp_path):
    """Old event payloads have no 'sources' key — replay must apply them."""
    from sas_lineage.store import build_bundle
    sas = tmp_path / "a.sas"
    sas.write_text("data work.a; set work.x; run;")
    with LineageStore(tmp_path / "db.duckdb") as store:
        bundle = build_bundle(sas, tmp_path)
        bundle.pop("sources")
        store.apply_bundle(bundle)   # replay path: no event written
        files = store.con.execute("SELECT count(*) FROM files").fetchone()[0]
    assert files == 1


def test_remove_file_deletes_all_rows_and_replays(tmp_path):
    sas = tmp_path / "a.sas"
    sas.write_text("data work.a; set work.x; run;")
    sessions = tmp_path / "sessions"
    with LineageStore(tmp_path / "db1.duckdb") as store:
        fileid = store.ingest_file(sas, tmp_path)
        store.remove_file(fileid)
        for table in ("files", "blocks", "lineage", "sources"):
            assert store.con.execute(
                f"SELECT count(*) FROM {table}").fetchone()[0] == 0, table
        store.export_session_events(sessions)
    with LineageStore(tmp_path / "db2.duckdb") as fresh:
        fresh.consolidate_sessions(sessions)
        assert fresh.con.execute("SELECT count(*) FROM files").fetchone()[0] == 0


# ---- freshness (store-freshness plan, Task 4) -------------------------------

def _flows(store, fileid):
    return store.con.execute(
        "SELECT source_canonical_name, target_canonical_name, freshness "
        "FROM lineage WHERE fileid = ? ORDER BY 1, 2", [fileid]).fetchall()


def test_first_ingest_is_all_green(tmp_path):
    sas = tmp_path / "a.sas"
    sas.write_text("data work.a; set work.x; run;")
    with LineageStore(tmp_path / "db.duckdb") as store:
        fileid = store.ingest_file(sas, tmp_path)
        assert _flows(store, fileid) == [("work.x", "work.a", "green")]


def test_unchanged_block_stays_green_on_reingest(tmp_path):
    sas = tmp_path / "a.sas"
    sas.write_text("data work.a; set work.x; run;")
    with LineageStore(tmp_path / "db.duckdb") as store:
        fileid = store.ingest_file(sas, tmp_path)
        store.ingest_file(sas, tmp_path)              # same bytes
        assert _flows(store, fileid) == [("work.x", "work.a", "green")]


def test_cosmetic_block_change_is_yellow(tmp_path):
    sas = tmp_path / "a.sas"
    sas.write_text("data work.a; set work.x; run;")
    with LineageStore(tmp_path / "db.duckdb") as store:
        fileid = store.ingest_file(sas, tmp_path)
        sas.write_text("data work.a; set work.x; label a='edited'; run;")
        store.ingest_file(sas, tmp_path)              # new hash, same flow
        assert _flows(store, fileid) == [("work.x", "work.a", "yellow")]


def test_new_flow_in_changed_block_is_red_and_lost_flow_recorded(tmp_path):
    sas = tmp_path / "a.sas"
    sas.write_text("data work.a; set work.x; run;")
    with LineageStore(tmp_path / "db.duckdb") as store:
        fileid = store.ingest_file(sas, tmp_path)
        sas.write_text("data work.b; set work.y; run;")
        store.ingest_file(sas, tmp_path)
        assert _flows(store, fileid) == [("work.y", "work.b", "red")]
        lost = store.con.execute(
            "SELECT src, dst, level FROM lost_flows WHERE fileid = ?",
            [fileid]).fetchall()
        assert lost == [("work.x", "work.a", "block")]


def test_lost_flow_clears_when_it_reappears(tmp_path):
    sas = tmp_path / "a.sas"
    sas.write_text("data work.a; set work.x; run;")
    with LineageStore(tmp_path / "db.duckdb") as store:
        fileid = store.ingest_file(sas, tmp_path)
        sas.write_text("data work.b; set work.y; run;")
        store.ingest_file(sas, tmp_path)
        sas.write_text("data work.a; set work.x; run;")
        store.ingest_file(sas, tmp_path)              # the flow is back
        # the reappeared flow's ghost is gone...
        assert store.con.execute(
            "SELECT count(*) FROM lost_flows WHERE fileid = ? "
            "AND src = 'work.x'", [fileid]).fetchone()[0] == 0
        # ...and the interim flow, lost by the revert, is the ghost now
        assert store.con.execute(
            "SELECT src, dst FROM lost_flows WHERE fileid = ?",
            [fileid]).fetchall() == [("work.y", "work.b")]
