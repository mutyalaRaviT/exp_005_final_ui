"""SAS Dependency Explorer — data builder and HTML generator.

Produces a fully self-contained HTML page (vendor libraries inlined, data
embedded as JSON) and can also embed that page as a new tab inside an
existing report (the base64-iframe mechanism the report already uses).

conversion_status per file (model extracted from the conversion-status page
of the EDW report): every block converted -> "converted", some -> "partial",
none -> "not converted". Coverage is "parsed_blocks / total_blocks".
"""
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from sas_lineage.exporter import make_fileid, relative_folder, schema_of
from sas_lineage.models import BLOCK_FLOW, FILE_FLOW
from sas_lineage.pipeline import analyze_file

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
TEMPLATE = UI_DIR / "template.html"
VENDOR = UI_DIR / "vendor"

# The three vendor libraries, in load order (elk must precede cytoscape-elk).
VENDOR_FILES = ["elk.bundled.js", "cytoscape.min.js", "cytoscape-elk.js"]


def conversion_status(blocks: list[dict]) -> str:
    parsed = sum(1 for b in blocks if b["status"] == "PARSED")
    if not blocks or parsed == 0:
        return "not converted"
    if parsed == len(blocks):
        return "converted"
    return "partial"


def _edge_row(edge, names: dict[str, dict]) -> dict:
    src, dst = names[edge.source], names[edge.target]
    return {
        "block": dst["block"],
        "src_ref": src["ref"], "dst_ref": dst["ref"],
        "src_name": src["name"], "dst_name": dst["name"],
    }


def build_file_entry(path: Path, base_dir: Path) -> dict:
    """Analyze one SAS file into the UI's per-file record."""
    analysis = analyze_file(path, registry_path=None)
    source = path.read_text()

    occurrence_info = {
        o.display: {"ref": o.id, "name": o.canonical, "block": o.block_id}
        for b in analysis.blocks
        for o in [*b.reads, *b.writes]
    }
    blocks = [
        {"id": b.block_id, "status": b.status,
         "kind": b.kind,
         "reads": len(b.reads), "writes": len(b.writes),
         "occurrences": [
             {"id": o.id, "name": o.canonical, "role": o.role}
             for o in [*b.reads, *b.writes]
         ]}
        for b in analysis.blocks
    ]
    reads = sorted({o.canonical for b in analysis.blocks for o in b.reads})
    writes = sorted({o.canonical for b in analysis.blocks for o in b.writes})
    folder = relative_folder(path, base_dir)

    return {
        "fileid": make_fileid(path, base_dir),
        "name": path.name,
        "folder": folder,
        "path": str(path),
        "loc": sum(1 for line in source.splitlines() if line.strip()),
        "blocks": blocks,
        "conversion_status": conversion_status(blocks),
        "coverage": f"{sum(1 for b in blocks if b['status'] == 'PARSED')}/{len(blocks)}",
        "reads": reads,
        "writes": writes,
        "schemas": sorted({schema_of(t) for t in [*reads, *writes]}),
        "code": source,
        "block_edges": [_edge_row(e, occurrence_info) for e in analysis.edges
                        if e.edge_type == BLOCK_FLOW],
        "file_edges": [_edge_row(e, occurrence_info) for e in analysis.edges
                       if e.edge_type == FILE_FLOW],
        # the verify views' extras — which blocks each macro call produced,
        # and what %include pulled in (or failed to)
        "macro_calls": [
            {"name": c.name, "instance": c.instance,
             "block_ids": sorted(
                 b.block_id for b in analysis.blocks
                 if b.block_id.startswith(f"{c.def_block_id}#{c.instance}"))}
            for c in analysis.macro_calls
        ],
        # resolved includes come back as absolute paths — show them the way
        # the source names them (relative to the including file); missing
        # ones are already the raw names the source used
        "includes": [
            os.path.relpath(p, path.parent) if os.path.isabs(p) else p
            for p in analysis.includes
        ],
        "missing_includes": list(analysis.missing_includes),
    }


def project_edges(files: list[dict]) -> list[dict]:
    """Cross-file dependencies: file A writes a table that file B reads.
    Single pass over a table -> writers/readers index."""
    writers: dict[str, list[str]] = {}
    readers: dict[str, list[str]] = {}
    for f in files:
        for table in f["writes"]:
            writers.setdefault(table, []).append(f["fileid"])
        for table in f["reads"]:
            readers.setdefault(table, []).append(f["fileid"])

    edges: dict[tuple[str, str], set[str]] = {}
    for table, writing_files in writers.items():
        for src in writing_files:
            for dst in readers.get(table, []):
                if src != dst:
                    edges.setdefault((src, dst), set()).add(table)
    return [
        {"src_file": src, "dst_file": dst, "tables": sorted(tables)}
        for (src, dst), tables in sorted(edges.items())
    ]


def project_edges_blocks(files: list[dict]) -> list[dict]:
    """Cross-file dependencies at block granularity: for each table, the
    LATEST writer block in the source file -> every reader block in each
    other file. Dropping the block columns and grouping reproduces
    project_edges exactly (the tests assert that parity)."""
    latest_writer: dict[tuple[str, str], dict] = {}
    readers: dict[str, list[tuple[str, dict]]] = {}
    for f in files:
        for block in f["blocks"]:
            for occ in block["occurrences"]:
                spot = {"block": block["id"], "ref": occ["id"]}
                if occ["role"] == "write":
                    latest_writer[(f["fileid"], occ["name"])] = spot
                else:
                    readers.setdefault(occ["name"], []).append((f["fileid"], spot))

    links = [
        {"src_file": src_file, "src_block": w["block"], "src_ref": w["ref"],
         "dst_file": dst_file, "dst_block": r["block"], "dst_ref": r["ref"],
         "table": table}
        for (src_file, table), w in latest_writer.items()
        for dst_file, r in readers.get(table, [])
        if src_file != dst_file
    ]
    links.sort(key=lambda l: (l["src_file"], l["src_block"],
                              l["dst_file"], l["dst_block"], l["table"]))
    return links


def build_ui_data(sas_paths: list[str | Path]) -> dict:
    # resolve first so relative CLI paths group into the right folders
    paths = [Path(p).resolve() for p in sas_paths]
    base_dir = Path(*_common_parts([p.parent for p in paths])) if paths else None
    files = [build_file_entry(p, base_dir) for p in sorted(paths)]
    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files": files,
        "project_edges": project_edges(files),
    }


def _common_parts(dirs: list[Path]) -> list[str]:
    parts_list = [d.resolve().parts for d in dirs]
    common = []
    for parts in zip(*parts_list):
        if len(set(parts)) == 1:
            common.append(parts[0])
        else:
            break
    return common


def export_ui(sas_paths: list[str | Path], out_path: str | Path) -> Path:
    """Write the standalone explorer HTML (data + vendor libs inlined)."""
    html = TEMPLATE.read_text()
    # escape "</" so SAS code containing "</script>" cannot terminate the
    # inline <script> element and blank the page
    data_json = json.dumps(build_ui_data(sas_paths)).replace("</", "<\\/")
    html = html.replace("/*__DATA_JSON__*/null", data_json)
    vendor_js = "\n;\n".join((VENDOR / name).read_text() for name in VENDOR_FILES)
    html = html.replace("/*__VENDOR_JS__*/", vendor_js)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    return out_path


# ---- embedding into an existing tabbed report -------------------------------

_BTN_MARK = "<!--SASDEPS_BTN-->"
_START_MARK = "<!--SASDEPS_START-->"
_END_MARK = "<!--SASDEPS_END-->"
_ANCHOR_BTN = "<button class=\"tab-btn\" onclick=\"switchTab('conversion')\">Conversion Status</button>"


def embed_into_report(report_path: str | Path, ui_html_path: str | Path) -> Path:
    """Add (or refresh) a 'SAS Dependencies' tab in the report, using the
    report's own base64-iframe pattern. Idempotent: re-running replaces the
    previously embedded tab."""
    report_path, ui_html_path = Path(report_path), Path(ui_html_path)
    report = report_path.read_text()
    payload = base64.b64encode(ui_html_path.read_bytes()).decode()

    # the report's switchTab() finds the active button by EXACT onclick match,
    # so the attribute must be exactly switchTab('sasdeps'); the iframe loader
    # is attached as an extra listener from the injected block below.
    button = (
        f'{_BTN_MARK}<button id="sasdeps-btn" class="tab-btn" '
        f"onclick=\"switchTab('sasdeps')\">SAS Dependencies</button>"
    )
    block = f"""{_START_MARK}
<div id="tab-sasdeps" class="tab-content" style="padding:0;max-width:none">
<iframe id="sasdeps-frame" style="width:100%;height:calc(100vh - 90px);border:none" frameborder="0"></iframe>
</div>
<script>window._sasDepsB64="{payload}";
window._loadSasDeps=function(){{
  if(window._sasDepsLoaded)return;
  var frame=document.getElementById('sasdeps-frame');
  var html=b64Utf8ToString(window._sasDepsB64);
  frame.src=URL.createObjectURL(new Blob([html],{{type:'text/html;charset=utf-8'}}));
  window._sasDepsLoaded=true;
}};
document.getElementById('sasdeps-btn').addEventListener('click',function(){{window._loadSasDeps();}});
</script>
{_END_MARK}"""

    # refresh previous embed, if any
    if _BTN_MARK in report:
        head, rest = report.split(_BTN_MARK, 1)
        report = head + rest.split("</button>", 1)[1]
    if _START_MARK in report:
        head, rest = report.split(_START_MARK, 1)
        report = head + rest.split(_END_MARK, 1)[1]

    if _ANCHOR_BTN not in report:
        raise ValueError("report has no Conversion Status tab button to anchor on")
    report = report.replace(_ANCHOR_BTN, _ANCHOR_BTN + button, 1)

    footer_anchor = '<div style="padding:0 40px;max-width:1400px;margin:0 auto">\n<footer>'
    if footer_anchor not in report:
        raise ValueError("report footer anchor not found")
    report = report.replace(footer_anchor, block + "\n" + footer_anchor, 1)

    report_path.write_text(report)
    return report_path


def collect_sas_paths(inputs: list[str | Path]) -> list[Path]:
    """Expand any directories among the inputs into their .sas files
    (recursive, sorted); plain files pass through in the order given."""
    paths: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            paths.extend(sorted(p.rglob("*.sas")))
        else:
            paths.append(p)
    return paths


def default_out_path(inputs: list[str | Path]) -> Path:
    """output/<sourcename>_<date_time_iso>.html — a fresh report per run.

    sourcename is the first input's folder name (or file stem); the timestamp
    is ISO-like with dashes so the name is safe on every filesystem."""
    first = Path(inputs[0])
    source = first.name if first.is_dir() else first.stem
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    return Path("output") / f"{source}_{stamp}.html"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: python -m sas_lineage.ui_export <file.sas|input-dir> [...]"
              " [--out <out.html>] [--embed <report.html>]\n"
              "  Without --out, writes output/<sourcename>_<date_time_iso>.html",
              file=sys.stderr)
        return 64
    embed_target = None
    if "--embed" in argv:
        i = argv.index("--embed")
        embed_target = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    out_path = None
    if "--out" in argv:
        i = argv.index("--out")
        out_path = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    elif argv[0].endswith(".html"):  # legacy: <out.html> <file.sas> [...]
        out_path, argv = argv[0], argv[1:]
    sas_paths = collect_sas_paths(argv)
    if not sas_paths:
        print("no .sas files found in the given inputs", file=sys.stderr)
        return 64
    out = export_ui(sas_paths, out_path or default_out_path(argv))
    print(f"written: {out}")
    if embed_target:
        embed_into_report(embed_target, out)
        print(f"embedded into: {embed_target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
