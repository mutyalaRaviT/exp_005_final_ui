"""pipeline.datamatch — Phase D DataMatch harness (language-agnostic).

Usage:
    python3 -m pipeline.datamatch <lang> [--stem X]

For every corpus/<lang>/**/*.io.json manifest (optionally narrowed to one
--stem), this locates that source file's REFERENCE outputs and CONVERTED
outputs, normalizes both per the DataMatch law, compares them as row
multisets, and writes:

  - reports/e2e_status.json  — merged across langs+runs, see merge_report()
  - reports/datamatch.html   — a plain self-contained verdict table

This module holds NO codegen knowledge and no per-language term shapes —
it never imports anything from pipeline/codegen or pipeline/term_parse.
Everything it does is generic filesystem/CSV/text work:

  - reference layout: probe two known shapes (a directory of part files,
    e.g. pig's out/pig/<stem>/<name>/part-*, or a single CSV file, e.g.
    hive's out/hive_ref/<stem>/<name>.csv) and use whichever exists —
    resolve_ref_target() names no language.
  - converted layout: always a directory of CSV part files,
    out/pyspark_out/<lang>/<stem>/<name>/ — the one place "pyspark" is
    mentioned, and only as a path segment, not as branching logic.
  - BlockId attribution: scan each node4 term's TEXT for the output name
    as a whole identifier and take the last (highest-seq) block that
    mentions it — attribute_block() does not know what "store" or
    "create_table_as" mean; it works by string matching alone, so it
    covers pig, hive, and any future language's terms without an edit.

DataMatch law (verbatim from the phase contract): compare row SETS after
normalization — sort rows (irrelevant once compared as multisets), strip
whitespace, floats rounded to 6 decimals, ints unified — column order
follows the manifest's schema (the manifest is read positionally: schema
order IS column order, so no reordering step is needed here).

Verdicts, per output: PASS | FAIL | REF_MISSING | CONV_MISSING.
  - REF_MISSING wins over CONV_MISSING when both are absent: without a
    reference there is nothing to compare against, so "did we convert it"
    is moot.
File-level verdict = the worst of its outputs, in this priority order:
    FAIL > REF_MISSING > CONV_MISSING > PASS.

Run: python3 -m pipeline.datamatch pig
     python3 -m pipeline.datamatch hive --stem h01_create_select
     python3 -m pipeline.tests.test_datamatch   (this module's own proof)
"""
import argparse
import csv
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

FLOAT_DP = 6

_CONTROL_NAMES = {"_SUCCESS"}
_CONTROL_SUFFIXES = (".crc",)


def _is_control_file(name: str) -> bool:
    """_SUCCESS, dotfiles (.crc sidecars, .DS_Store, ...), and *.crc are
    never row data — every Hadoop/Spark part-file directory carries them."""
    if name in _CONTROL_NAMES:
        return True
    if name.startswith("."):
        return True
    if name.endswith(_CONTROL_SUFFIXES):
        return True
    return False


def read_rows(target):
    """Read CSV rows from a reference/converted output target.

    `target` is a Path that is either:
      - a single CSV file (e.g. hive_ref's <name>.csv), or
      - a directory of CSV part files (pig / pyspark_out style), whose
        non-control files are concatenated in filename-sorted order.

    Returns None if `target` is None or does not exist on disk — the
    caller turns that into a REF_MISSING / CONV_MISSING verdict rather
    than a crash. Returns [] for a target that exists but holds no rows.
    """
    if target is None or not target.exists():
        return None
    if target.is_file():
        files = [target]
    else:
        files = sorted(
            f for f in target.iterdir()
            if f.is_file() and not _is_control_file(f.name)
        )
    rows = []
    for f in files:
        with f.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.reader(fh):
                if row:  # skip fully blank lines
                    rows.append(row)
    return rows


def _drop_header_if_present(rows, schema_names):
    """Best-effort: if the first row IS the schema's column names (case-
    insensitive, "name:type" -> "name"), drop it as a header a writer
    added. The DataMatch law's reference files are headerless by
    contract; this only guards against a converted-side writer that
    chose header=True, so it doesn't masquerade as a real mismatch."""
    if not rows or not schema_names:
        return rows
    first = [c.strip().lower() for c in rows[0]]
    names = [str(n).split(":", 1)[0].strip().lower() for n in schema_names]
    if first == names:
        return rows[1:]
    return rows


def normalize_value(v):
    """One field -> its canonical comparable string, per the DataMatch law:
    whitespace stripped; numeric strings rounded to FLOAT_DP decimals with
    ints and whole floats unified ("5" == "5.0" == "5.000000"); non-numeric
    strings pass through stripped and otherwise unchanged.

    Non-finite numerics are canonicalized BEFORE the rounding step, for two
    reasons. First, correctness: round()/int() raise on NaN and Inf, so
    without this a single NaN cell (Spark writes 0.0/0.0 as "NaN", DuckDB
    writes it as "nan") would crash the whole DataMatch run instead of
    producing a verdict. Second, fairness: the two engines spell the same
    value differently ("NaN"/"nan", "Infinity"/"inf"), and a spelling
    difference is not a data difference — collapsing both sides to one
    token makes NaN match NaN and +Inf match +Inf while still keeping
    NaN, +Inf and -Inf distinct from each other and from every real
    number."""
    s = str(v).strip()
    try:
        f = float(s)
    except ValueError:
        return s
    if math.isnan(f):
        return "nan"
    if math.isinf(f):
        return "inf" if f > 0 else "-inf"
    r = round(f, FLOAT_DP)
    if r == 0:
        r = 0.0  # collapse -0.0 -> 0.0
    if r == int(r):
        return str(int(r))
    return format(r, f".{FLOAT_DP}f").rstrip("0").rstrip(".")


def normalize_row(row):
    return tuple(normalize_value(v) for v in row)


def compare_rows(ref_rows, conv_rows, max_samples=5):
    """Multiset row comparison. Returns (verdict, n_mismatch, samples):
    verdict is PASS or FAIL; n_mismatch is the total count of row-
    instances that differ (duplicates counted, per multiset semantics);
    samples is up to `max_samples` dicts naming a mismatched row and how
    many times each side has it."""
    ref_counts = Counter(normalize_row(r) for r in ref_rows)
    conv_counts = Counter(normalize_row(r) for r in conv_rows)
    if ref_counts == conv_counts:
        return "PASS", 0, []

    missing_in_conv = ref_counts - conv_counts  # ref has more instances
    extra_in_conv = conv_counts - ref_counts    # conv has more instances
    n_mismatch = sum(missing_in_conv.values()) + sum(extra_in_conv.values())

    samples = []
    for row in missing_in_conv:
        samples.append({
            "row": list(row),
            "ref_count": ref_counts[row],
            "conv_count": conv_counts.get(row, 0),
        })
        if len(samples) >= max_samples:
            break
    if len(samples) < max_samples:
        for row in extra_in_conv:
            samples.append({
                "row": list(row),
                "ref_count": ref_counts.get(row, 0),
                "conv_count": conv_counts[row],
            })
            if len(samples) >= max_samples:
                break
    return "FAIL", n_mismatch, samples


_NAME_PATTERN_CACHE = {}


def _name_pattern(name):
    pat = _NAME_PATTERN_CACHE.get(name)
    if pat is None:
        pat = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)")
        _NAME_PATTERN_CACHE[name] = pat
    return pat


def attribute_block(node4_terms, output_name):
    """Which BlockId's term text mentions `output_name` LAST (by seq)?

    Language-agnostic by construction: this does not parse the term or
    know what "store"/"create_table_as"/etc. mean. It just looks for the
    output name written as a whole identifier — a bare atom like
    rel(out_pass) or inside a quoted path like lit('.../out_pass') both
    match, because the characters on either side of the name are non-word
    characters either way. The block that actually persists a name is
    always the last block to mention it, so "last match by seq" recovers
    the producing BlockId without any per-language table.
    """
    pat = _name_pattern(output_name)
    best_block, best_seq = None, None
    for entry in sorted(node4_terms, key=lambda e: e.get("seq", 0)):
        if pat.search(entry.get("term", "")):
            seq = entry.get("seq", 0)
            if best_seq is None or seq >= best_seq:
                best_seq, best_block = seq, entry.get("block")
    return best_block


def load_node4(ir_root, lang, stem):
    path = Path(ir_root) / lang / f"{stem}.node4.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def find_manifests(corpus_root, lang, stem_filter=None):
    lang_dir = Path(corpus_root) / lang
    if not lang_dir.is_dir():
        return []
    manifests = sorted(lang_dir.rglob("*.io.json"))
    if not stem_filter:
        return manifests
    out = []
    for m in manifests:
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        stem = Path(data.get("file", m.name)).stem
        if stem == stem_filter:
            out.append(m)
    return out


def resolve_ref_target(ref_root, stem, name):
    """Probe both known reference layouts and use whichever exists:
      - <ref_root>/<stem>/<name>/       a directory of part files (pig)
      - <ref_root>/<stem>/<name>.csv    a single CSV file (hive)
    No language name appears here — pure filesystem probing, so a third
    language's reference layout works automatically if it matches either
    shape, and is REF_MISSING (not a crash) if it matches neither."""
    d = Path(ref_root) / stem / name
    if d.exists():
        return d
    f = Path(ref_root) / stem / f"{name}.csv"
    if f.exists():
        return f
    return None


def resolve_conv_target(conv_root, lang, stem, name):
    """Converted outputs are always a directory of CSV part files, per the
    layout law: out/pyspark_out/<lang>/<stem>/<output_name>/"""
    return Path(conv_root) / lang / stem / name


def _rollup_file_verdict(output_results):
    verdicts = {o["verdict"] for o in output_results}
    for v in ("FAIL", "REF_MISSING", "CONV_MISSING"):
        if v in verdicts:
            return v
    return "PASS"


def process_manifest(manifest_path, lang, ir_root, ref_root, conv_root):
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    src_file = data.get("file", str(manifest_path))
    stem = Path(src_file).stem
    node4_terms = load_node4(ir_root, lang, stem)

    outputs = []
    for out in data.get("outputs", []):
        name = out["name"]
        schema = out.get("schema", [])
        ref_target = resolve_ref_target(ref_root, stem, name)
        conv_target = resolve_conv_target(conv_root, lang, stem, name)
        ref_rows = read_rows(ref_target)
        conv_rows = read_rows(conv_target)
        if ref_rows is not None:
            ref_rows = _drop_header_if_present(ref_rows, schema)
        if conv_rows is not None:
            conv_rows = _drop_header_if_present(conv_rows, schema)

        block = attribute_block(node4_terms, name)

        if ref_rows is None:
            outputs.append({
                "name": name, "verdict": "REF_MISSING",
                "rows_ref": None,
                "rows_conv": (len(conv_rows) if conv_rows is not None else None),
                "n_mismatch": None, "block": block, "sample_mismatches": [],
            })
            continue
        if conv_rows is None:
            outputs.append({
                "name": name, "verdict": "CONV_MISSING",
                "rows_ref": len(ref_rows), "rows_conv": None,
                "n_mismatch": None, "block": block, "sample_mismatches": [],
            })
            continue

        verdict, n_mismatch, samples = compare_rows(ref_rows, conv_rows)
        outputs.append({
            "name": name, "verdict": verdict,
            "rows_ref": len(ref_rows), "rows_conv": len(conv_rows),
            "n_mismatch": n_mismatch, "block": block,
            "sample_mismatches": samples,
        })

    return {
        "file": src_file,
        "verdict": _rollup_file_verdict(outputs),
        "outputs": outputs,
    }


def run(lang, stem=None, corpus_root=Path("corpus"), ir_root=Path("out/ir"),
        ref_root=None, conv_root=Path("out/pyspark_out")):
    """Evaluate every (optionally one --stem) manifest for `lang` and
    return the {"lang","generated_at_run","files":[...]} record — the
    per-run shape merge_report() files under report[lang]."""
    if ref_root is None:
        # pig's real reference trees already live at out/pig (pig -x local
        # output, not a harness-owned mirror); every other language gets a
        # harness-owned out/<lang>_ref, e.g. hive -> out/hive_ref.
        ref_root = Path("out/pig") if lang == "pig" else Path("out") / f"{lang}_ref"
    manifests = find_manifests(corpus_root, lang, stem)
    files = [
        process_manifest(m, lang, ir_root, ref_root, conv_root)
        for m in manifests
    ]
    return {
        "lang": lang,
        "generated_at_run": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": files,
    }


def merge_report(report_path, lang, new_data):
    """reports/e2e_status.json holds every language's latest run keyed by
    lang name: {"pig": {...}, "hive": {...}}. Writing one lang's results
    only ever replaces that lang's own key, so a hive run never clobbers
    a pig run recorded earlier (or vice versa)."""
    existing = {}
    if report_path.exists():
        try:
            existing = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    if not isinstance(existing, dict):
        existing = {}
    existing[lang] = new_data
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return existing


_VERDICT_COLORS = {
    "PASS": "#1a7f37",
    "FAIL": "#cf222e",
    "REF_MISSING": "#9a6700",
    "CONV_MISSING": "#9a6700",
}


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(merged):
    """Plain self-contained HTML: file -> outputs -> verdict, green/red
    cells, mismatch samples. Simple by design — the contract says the IDE
    re-skins this later; this only needs to be honest and readable."""
    sections = []
    for lang in sorted(merged.keys()):
        lang_data = merged[lang]
        sections.append(
            f'<h2>{_esc(lang)} '
            f'<span class="ts">generated_at_run: {_esc(lang_data.get("generated_at_run", ""))}</span></h2>'
        )
        for f in lang_data.get("files", []):
            fv = f.get("verdict", "")
            color = _VERDICT_COLORS.get(fv, "#57606a")
            sections.append(
                f'<h3>{_esc(f.get("file", ""))} '
                f'<span class="badge" style="background:{color}">{_esc(fv)}</span></h3>'
            )
            rows = [
                "<table><thead><tr>"
                "<th>output</th><th>verdict</th><th>block</th>"
                "<th>rows_ref</th><th>rows_conv</th><th>n_mismatch</th>"
                "<th>sample mismatches</th></tr></thead><tbody>"
            ]
            for o in f.get("outputs", []):
                ov = o.get("verdict", "")
                ocolor = _VERDICT_COLORS.get(ov, "#57606a")
                samples = o.get("sample_mismatches") or []
                samples_txt = "; ".join(
                    f'row={_esc(s.get("row"))} ref={_esc(s.get("ref_count"))} conv={_esc(s.get("conv_count"))}'
                    for s in samples
                ) or "&mdash;"
                rows.append(
                    "<tr>"
                    f'<td>{_esc(o.get("name"))}</td>'
                    f'<td><span class="badge" style="background:{ocolor}">{_esc(ov)}</span></td>'
                    f'<td>{_esc(o.get("block"))}</td>'
                    f'<td>{_esc(o.get("rows_ref"))}</td>'
                    f'<td>{_esc(o.get("rows_conv"))}</td>'
                    f'<td>{_esc(o.get("n_mismatch"))}</td>'
                    f'<td class="samples">{samples_txt}</td>'
                    "</tr>"
                )
            rows.append("</tbody></table>")
            sections.append("\n".join(rows))
    body = "\n".join(sections) if sections else "<p>No DataMatch runs recorded yet.</p>"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>exp_014 DataMatch report</title>
<style>
body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 2rem; color: #1f2328; background: #fff; }}
h2 {{ margin-top: 2rem; border-bottom: 2px solid #d0d7de; padding-bottom: .25rem; }}
h3 {{ margin-top: 1.5rem; font-size: 1rem; }}
.ts {{ font-weight: normal; font-size: .8rem; color: #57606a; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: .5rem; }}
th, td {{ border: 1px solid #d0d7de; padding: .35rem .5rem; font-size: .85rem; text-align: left; vertical-align: top; }}
th {{ background: #f6f8fa; }}
.badge {{ color: #fff; border-radius: 4px; padding: .1rem .5rem; font-weight: 600; font-size: .78rem; }}
.samples {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .78rem; }}
</style></head>
<body>
<h1>exp_014 DataMatch report</h1>
{body}
</body></html>"""


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m pipeline.datamatch")
    ap.add_argument("lang", help="language name, e.g. pig or hive")
    ap.add_argument("--stem", default=None, help="restrict to one source file stem")
    ap.add_argument("--corpus-root", default="corpus")
    ap.add_argument("--ir-root", default="out/ir")
    ap.add_argument("--ref-root", default=None,
                     help="default: out/pig for lang=pig, else out/<lang>_ref")
    ap.add_argument("--conv-root", default="out/pyspark_out")
    ap.add_argument("--report", default="reports/e2e_status.json")
    ap.add_argument("--html", default="reports/datamatch.html")
    args = ap.parse_args(argv)

    ref_root = Path(args.ref_root) if args.ref_root else None
    new_data = run(
        args.lang, stem=args.stem,
        corpus_root=Path(args.corpus_root), ir_root=Path(args.ir_root),
        ref_root=ref_root, conv_root=Path(args.conv_root),
    )

    report_path = Path(args.report)
    merged = merge_report(report_path, args.lang, new_data)

    html_path = Path(args.html)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(merged), encoding="utf-8")

    files = new_data["files"]
    name_w = max((len(f["file"]) for f in files), default=4)
    print(f"{'file'.ljust(name_w)}  verdict")
    print(f"{'-' * name_w}  -------")
    n_outputs = 0
    all_pass = True
    for f in files:
        print(f"{f['file'].ljust(name_w)}  {f['verdict']}")
        for o in f["outputs"]:
            n_outputs += 1
            if o["verdict"] != "PASS":
                all_pass = False
            print(f"    {o['name']:<24} {o['verdict']:<14} block={o['block']} "
                  f"rows_ref={o['rows_ref']} rows_conv={o['rows_conv']} n_mismatch={o['n_mismatch']}")
    if n_outputs == 0:
        all_pass = False
        print(f"ERROR: no outputs evaluated for lang={args.lang!r} "
              f"(no manifests found under {args.corpus_root}/{args.lang}?)", file=sys.stderr)

    print()
    print(f"wrote {report_path}")
    print(f"wrote {html_path}")
    print(f"ALL PASS: {'true' if all_pass else 'false'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
