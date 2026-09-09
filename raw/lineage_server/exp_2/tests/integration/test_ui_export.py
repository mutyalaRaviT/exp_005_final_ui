"""Integration tests for the SAS Dependency Explorer generator."""
import json
import re
from pathlib import Path

import pytest

from sas_lineage.ui_export import (
    build_file_entry,
    build_ui_data,
    collect_sas_paths,
    conversion_status,
    default_out_path,
    embed_into_report,
    export_ui,
    main,
    project_edges,
    project_edges_blocks,
)

EXAMPLES = Path(__file__).resolve().parent.parent.parent / "examples"
ALL_SAS = sorted(EXAMPLES.rglob("*.sas"))


def test_conversion_status_model():
    assert conversion_status([{"status": "PARSED"}]) == "converted"
    assert conversion_status([{"status": "PARSED"}, {"status": "PARTIAL"}]) == "partial"
    assert conversion_status([{"status": "NOT_MATCHED"}]) == "not converted"
    assert conversion_status([]) == "not converted"


def test_build_ui_data_files_and_edges():
    data = build_ui_data(ALL_SAS)
    assert len(data["files"]) == len(ALL_SAS)
    folders = {f["folder"] for f in data["files"]}
    assert {"examples", "landing", "staging", "mart"} <= folders
    pairs = {(e["src_file"].split("#")[0], e["dst_file"].split("#")[0])
             for e in data["project_edges"]}
    assert ("landing/load_customers.sas", "staging/build_summary.sas") in pairs
    assert ("landing/load_orders.sas", "staging/build_summary.sas") in pairs


def test_project_edges_no_self_loops():
    data = build_ui_data(ALL_SAS)
    assert all(e["src_file"] != e["dst_file"] for e in data["project_edges"])


def test_export_ui_is_self_contained(tmp_path):
    out = export_ui(ALL_SAS[:3], tmp_path / "explorer.html")
    html = out.read_text()
    assert "cytoscapeElk" in html          # vendor libs inlined
    assert "ELK" in html
    data = json.loads(
        re.search(r"const DATA = (\{.*?\});\n\nconst filesById", html, re.S).group(1))
    assert len(data["files"]) == 3
    assert "http://" not in html.split("</script>")[-1]  # no external fetches


MINI_REPORT = """<html><body>
<div class="tab-bar">
<button class="tab-btn" onclick="switchTab('conversion')">Conversion Status</button>
</div>
<div style="padding:0 40px;max-width:1400px;margin:0 auto">
<footer>x</footer></div>
<script>function switchTab(n){}</script>
</body></html>"""


def test_embed_into_report_idempotent(tmp_path):
    ui = export_ui(ALL_SAS[:2], tmp_path / "ui.html")
    report = tmp_path / "report.html"
    report.write_text(MINI_REPORT)

    embed_into_report(report, ui)
    once = report.read_text()
    assert once.count("SAS Dependencies") == 1
    assert 'onclick="switchTab(\'sasdeps\')"' in once  # exact-match onclick
    assert "_sasDepsB64" in once

    embed_into_report(report, ui)  # run again: replaced, not duplicated
    twice = report.read_text()
    assert twice.count("SAS Dependencies") == 1
    assert twice.count("_sasDepsB64=") == 1


def test_embed_requires_anchor(tmp_path):
    ui = export_ui(ALL_SAS[:1], tmp_path / "ui.html")
    bad = tmp_path / "bad.html"
    bad.write_text("<html><body>nothing here</body></html>")
    with pytest.raises(ValueError):
        embed_into_report(bad, ui)


def test_collect_sas_paths_expands_directories(tmp_path):
    (tmp_path / "sub").mkdir()
    a = tmp_path / "a.sas"
    b = tmp_path / "sub" / "b.sas"
    a.write_text("data w.a; run;")
    b.write_text("data w.b; run;")
    (tmp_path / "notes.txt").write_text("ignored")

    assert collect_sas_paths([tmp_path]) == [a, b]
    # plain files pass through untouched
    assert collect_sas_paths([a]) == [a]


def test_default_out_path_uses_source_and_timestamp(tmp_path):
    src = tmp_path / "ankitha_1"
    src.mkdir()
    out = default_out_path([src])
    assert out.parent == Path("output")
    # ankitha_1_YYYY-MM-DDTHH-MM-SS.html
    assert re.fullmatch(
        r"ankitha_1_\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.html", out.name)


def test_main_with_directory_writes_timestamped_report(tmp_path, monkeypatch, capsys):
    src = tmp_path / "proj_x"
    src.mkdir()
    (src / "one.sas").write_text("data work.t1; set work.t0; run;")
    monkeypatch.chdir(tmp_path)

    assert main([str(src)]) == 0
    written = Path(capsys.readouterr().out.split("written: ")[1].strip())
    assert written.exists()
    assert written.parent == Path("output")
    assert written.name.startswith("proj_x_")
    assert written.suffix == ".html"


# ---- verify payload (verify-views plan, Task 1) -----------------------------

def test_file_entry_carries_verify_payload(tmp_path):
    (tmp_path / "inc.sas").write_text("data work.pre; set raw.src; run;")
    (tmp_path / "main.sas").write_text(
        "%include 'inc.sas';\n"
        "%include 'gone.sas';\n"
        "%macro load(t); data work.&t; set raw.&t; run; %mend;\n"
        "%load(a);\n"
        "data work.b; set work.a; run;\n")
    entry = build_file_entry(tmp_path / "main.sas", tmp_path)

    assert entry["includes"] == ["inc.sas"]
    assert entry["missing_includes"] == ["gone.sas"]

    # every block lists its occurrences (id, canonical name, role)
    for block in entry["blocks"]:
        assert "occurrences" in block
        for occ in block["occurrences"]:
            assert set(occ) == {"id", "name", "role"}
            assert occ["role"] in ("read", "write")
    all_names = {o["name"] for b in entry["blocks"]
                 for o in b["occurrences"]}
    assert {"work.a", "raw.a", "work.b"} <= all_names

    # the macro call names the blocks its expansion produced
    (call,) = [c for c in entry["macro_calls"] if c["name"] == "load"]
    assert call["instance"] == 1
    assert call["block_ids"]
    block_ids = {b["id"] for b in entry["blocks"]}
    assert set(call["block_ids"]) <= block_ids


# ---- block-level cross-file edges (V2-1) ------------------------------------

def _entries(tmp_path, files: dict[str, str]):
    for name, code in files.items():
        (tmp_path / name).write_text(code)
    return [build_file_entry(tmp_path / name, tmp_path) for name in sorted(files)]


def test_blocklinks_link_latest_writer_block_to_reader_blocks(tmp_path):
    entries = _entries(tmp_path, {
        "a.sas": ("data work.t; set raw.x; run;\n"
                  "data work.t; set raw.y; run;"),      # two writers: latest wins
        "b.sas": "data work.out; set work.t; run;",
    })
    links = project_edges_blocks(entries)
    t_links = [l for l in links if l["table"] == "work.t"]
    assert len(t_links) == 1
    link = t_links[0]
    a_blocks = [b["id"] for b in entries[0]["blocks"]]
    assert link["src_file"].endswith("a.sas") and link["src_block"] == a_blocks[1]
    assert link["dst_file"].endswith("b.sas")
    assert link["src_ref"].startswith(link["src_block"] + ":t_")
    assert link["dst_ref"].startswith(link["dst_block"] + ":t_")


def test_blocklinks_collapse_to_project_edges(tmp_path):
    entries = _entries(tmp_path, {
        "a.sas": "data work.t; set raw.x; run;",
        "b.sas": ("data work.out; set work.t; run;\n"
                  "proc sort data=work.t out=work.srt; by k; run;"),
        "c.sas": "data work.more; set work.out; run;",
    })
    links = project_edges_blocks(entries)
    collapsed: dict[tuple[str, str], set[str]] = {}
    for l in links:
        collapsed.setdefault((l["src_file"], l["dst_file"]), set()).add(l["table"])
    expected = {(e["src_file"], e["dst_file"]): set(e["tables"])
                for e in project_edges(entries)}
    assert collapsed == expected
