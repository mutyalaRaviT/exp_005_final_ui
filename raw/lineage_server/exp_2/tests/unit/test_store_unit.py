"""Unit tests for the DuckDB store: bundles, upserts, enrichment, events."""
from pathlib import Path

import pytest

from sas_lineage.store import LineageStore, build_bundle, _block_source

ANNOTATED = """/*BLOCKID 1:111222333, Data Step, Lines: 4;*/
data work.out;
    set raw.src;
run;
/*ENDBLOCKID 1:111222333, Data Step;*/
"""


@pytest.fixture
def sas_file(tmp_path):
    f = tmp_path / "jobs" / "job_a.sas"
    f.parent.mkdir()
    f.write_text(ANNOTATED)
    return f


def test_build_bundle_shape(sas_file, tmp_path):
    bundle = build_bundle(sas_file, base_dir=tmp_path)
    assert bundle["file"]["sasfilename"] == "job_a.sas"
    assert bundle["file"]["folder_path"] == "jobs"
    assert bundle["file"]["conversion_status"] == "converted"
    assert [b["block_id"] for b in bundle["blocks"]] == ["1:111222333"]
    assert "data work.out" in bundle["blocks"][0]["sas_code"]
    row = bundle["lineage"][0]
    assert row["source_canonical_name"] == "raw.src"
    assert row["edge_type"] == "BLOCK_FLOW"
    assert row["folder_path"] == "jobs"


def test_block_source_only_for_injected_ids():
    assert "data work.out" in _block_source(ANNOTATED, "1:111222333")
    assert _block_source(ANNOTATED, "b_1") == ""
    assert _block_source(ANNOTATED, "1:111222333#1") == ""  # macro instance


def test_ingest_is_upsert_not_duplicate(sas_file, tmp_path):
    with LineageStore(tmp_path / "db.duckdb") as store:
        store.ingest_file(sas_file, base_dir=tmp_path)
        store.ingest_file(sas_file, base_dir=tmp_path)  # again
        assert store.con.execute("SELECT count(*) FROM files").fetchone()[0] == 1
        assert store.con.execute("SELECT count(*) FROM lineage").fetchone()[0] == 1
        # but both writes are in the event log
        assert store.con.execute("SELECT count(*) FROM events").fetchone()[0] == 2


def test_enrich_updates_and_logs(sas_file, tmp_path):
    with LineageStore(tmp_path / "db.duckdb") as store:
        fileid = store.ingest_file(sas_file, base_dir=tmp_path)
        store.enrich_file(fileid, conversion_status="verified")
        status = store.con.execute(
            "SELECT conversion_status FROM files WHERE fileid = ?", [fileid]
        ).fetchone()[0]
        assert status == "verified"
        kinds = [r[0] for r in store.con.execute(
            "SELECT event_type FROM events ORDER BY seq").fetchall()]
        assert kinds == ["file_ingested", "file_enriched"]


def test_enrich_rejects_unknown_column(sas_file, tmp_path):
    with LineageStore(tmp_path / "db.duckdb") as store:
        fileid = store.ingest_file(sas_file, base_dir=tmp_path)
        with pytest.raises(ValueError):
            store.enrich_file(fileid, loc=999)


def test_event_replay_reproduces_state(sas_file, tmp_path):
    with LineageStore(tmp_path / "a.duckdb", session_id="s1") as first:
        first.ingest_file(sas_file, base_dir=tmp_path)
        events = first.con.execute(
            "SELECT event_type, fileid, payload FROM events").fetchall()

    import json
    with LineageStore(tmp_path / "b.duckdb") as second:
        for event_type, fileid, payload in events:
            second._replay(event_type, fileid, json.loads(payload))
        assert second.con.execute("SELECT count(*) FROM files").fetchone()[0] == 1
        name = second.con.execute("SELECT sasfilename FROM files").fetchone()[0]
        assert name == "job_a.sas"
