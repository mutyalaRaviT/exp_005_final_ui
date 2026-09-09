"""Regression tests for review findings that span modules (4, 5, 7, 8)."""
import json
import re
from pathlib import Path

from sas_lineage.exporter import make_fileid, relative_folder
from sas_lineage.store import LineageStore, build_bundle
from sas_lineage.ui_export import build_ui_data, export_ui

JOB = "data work.out;\n set raw.src;\nrun;\n"


# 4. identical same-named files in different folders must not share a fileid
def test_fileid_distinct_for_identical_files_in_different_folders(tmp_path):
    for folder in ["etl", "reporting"]:
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "load.sas").write_text(JOB)
    a = make_fileid(tmp_path / "etl" / "load.sas", tmp_path)
    b = make_fileid(tmp_path / "reporting" / "load.sas", tmp_path)
    assert a != b
    assert a == "etl/load.sas"
    assert b == "reporting/load.sas"

    with LineageStore(tmp_path / "db.duckdb") as store:
        store.ingest_file(tmp_path / "etl" / "load.sas", base_dir=tmp_path)
        store.ingest_file(tmp_path / "reporting" / "load.sas", base_dir=tmp_path)
        assert store.con.execute("SELECT count(*) FROM files").fetchone()[0] == 2


# 5. pruning events must not reset the sequence (recovery orders by seq)
def test_event_sequence_survives_prune(tmp_path):
    job = tmp_path / "job.sas"
    job.write_text(JOB)
    with LineageStore(tmp_path / "db.duckdb") as store:
        store.ingest_file(job)  # seq 1
        store.con.execute("UPDATE events SET ts = now() - INTERVAL 60 DAY")
        store.prune_events(days=31)
        store.ingest_file(job)  # must be seq 2, not seq 1 again
        seqs = [r[0] for r in store.con.execute(
            "SELECT seq FROM events ORDER BY seq").fetchall()]
        assert seqs == [2]


# 7. SAS code containing </script> must not blank the explorer page
def test_export_ui_survives_script_terminator(tmp_path):
    hostile = tmp_path / "hostile.sas"
    hostile.write_text(
        "/* writes </script> markup */\ndata work.h;\n set raw.h;\nrun;\n")
    out = export_ui([hostile], tmp_path / "ui.html")
    html = out.read_text()
    payload = re.search(r"const DATA = (\{.*?\});\n\nconst filesById", html, re.S)
    assert payload, "DATA block missing"
    assert "</script> markup" not in payload.group(1)  # escaped as <\/script>
    data = json.loads(payload.group(1))                # still valid JSON
    assert "</script>" in data["files"][0]["code"]     # content preserved


# 8. relative CLI paths group into the correct folders
def test_relative_paths_group_correctly(tmp_path, monkeypatch):
    for project in ["projA", "projB"]:
        (tmp_path / project / "jobs").mkdir(parents=True)
        (tmp_path / project / "jobs" / f"{project}_x.sas").write_text(JOB)
    monkeypatch.chdir(tmp_path)
    data = build_ui_data(["projA/jobs/projA_x.sas", "projB/jobs/projB_x.sas"])
    folders = sorted(f["folder"] for f in data["files"])
    assert folders == ["projA/jobs", "projB/jobs"]


def test_relative_folder_shared_rule(tmp_path):
    f = tmp_path / "a" / "b" / "x.sas"
    f.parent.mkdir(parents=True)
    f.write_text(JOB)
    assert relative_folder(f, tmp_path) == str(Path("a") / "b")
    assert relative_folder(tmp_path / "a" / "b" / "x.sas", tmp_path / "a" / "b") == "b"
    assert relative_folder(f, None) == "b"
    # store and UI use the same helper -> same folder value
    bundle = build_bundle(f, base_dir=tmp_path)
    assert bundle["file"]["folder_path"] == relative_folder(f, tmp_path)
