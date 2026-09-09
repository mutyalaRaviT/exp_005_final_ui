"""server/bench_api.py — the logic behind the lineageQ Bench page (exp_42, 2026-09-07).

Why: bench.html shows one SAS program as aligned cell pairs (SAS block left, its PySpark
step right) and runs a pair on request: the left side through the executable node/4
(Rust or Prolog interpreter), the right side through the block's own PySpark program in
an attached Jupyter kernel (or locally), both on the block's Z3 inputs, judged by DataMatch.
Everything here shells out exactly as run_all.sh, loops/run_loops.sh and the studio do;
this file only sequences the steps per request and shapes the JSON the page reads.

Spec: docs/superpowers/specs/2026-09-07-bench-design.md

Public functions (all return plain dicts/lists, JSON-ready):
  list_files()                       files the dock shows + recent
  read_file(path)                    text of a file under ROOT
  open_program(path=None, sas=None)  the program as blocks + receipts + lineage
  lineage(stem)                      the lineage facts of an opened program
  run_block(stem, block, engine, session_id)
  similar(stem)                      programs with a similar signature (every SAS folder; unparsed files folded once into out/bench/sig)
  set_listing(stem, text|path), listing_verdicts(stem)   the pasted SAS listing vs the file-level Spark CSVs
  term(cmd, args, stem, block)       the allow-listed terminal
  Sessions: attach(url), list_sessions(), detach(id)
"""
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.datamatch import compare_rows  # noqa: E402

PY = ROOT / ".venv/bin/python"
RUST = ROOT / "rust_engine/target/release/lineageq_sas"
JAVA_HOME = os.environ.get("JAVA_HOME_17", "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")
BENCH = ROOT / "out/bench"
# 2026-09-08 team-finance-corpus, Task 5: the one corpus both oracles read now lives
# outside raw/bench_stack (see corpus/README.md), so confine()'s allow-list grows to
# include it.
CORPUS_ROOT = ROOT.parent.parent / "corpus"
PROGRAMS = {}          # stem -> the open_program() result (blocks, lineage), kept for run_block/term
_lock = threading.Lock()


def sh(cmd, cwd=ROOT, env=None, timeout=600):
    p = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, p.stdout, p.stderr


# ---------------------------------------------------------------- files
def confine(path):
    """A path under ROOT or under the shared corpus/ (CORPUS_ROOT), or ValueError. The
    page may only read what the repo, or the one corpus it shares with the rest of
    exp_005, holds."""
    p = (ROOT / path).resolve()
    for base in (ROOT, CORPUS_ROOT):
        if base in p.parents or p == base:
            return p
    raise ValueError(f"path outside the repo: {path}")


def _kind(p):
    return "sas" if p.suffix == ".sas" else "py" if p.suffix == ".py" else "ir"


def list_files():
    groups = []
    for d in ["../../corpus/team_finance/sas/raw", "raw", "out/pyspark_pretty", "out/ir/sas", "out/loops/lineage", "notebooks", "reports", "out/bench"]:
        dp = ROOT / d
        if not dp.is_dir():
            continue
        items = sorted(f for f in dp.iterdir() if f.suffix in (".sas", ".py", ".pl", ".ipynb", ".json", ".txt", ".html", ".csv", ".md") and not f.name.startswith("."))
        if items:
            groups.append({"dir": d, "items": [{"name": f.name, "path": f"{d}/{f.name}", "kind": _kind(f)} for f in items]})
    recent_f = BENCH / "recent.json"
    recent = json.loads(recent_f.read_text()) if recent_f.exists() else []
    return {"groups": groups, "recent": recent}


def note_recent(path):
    BENCH.mkdir(parents=True, exist_ok=True)
    f = BENCH / "recent.json"
    recent = json.loads(f.read_text()) if f.exists() else []
    recent = [path] + [r for r in recent if r != path]
    f.write_text(json.dumps(recent[:8]))


def read_file(path):
    p = confine(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    return {"path": path, "text": p.read_text(errors="replace"), "size": p.stat().st_size}


# exp_42 2026-09-08: folder aggregation page, saved buffers
IFRAME_MAX = 200 * 1024   # an HTML file this small opens as an iframe; bigger ones open as text in the buffer
BUFFERS = BENCH / "buffers"


def folder(d):
    """What a folder holds, one row per file: kind, size, modified; SAS files add blocks/edges (signature cache)
    and their bench receipts; HTML files say whether they fit an iframe."""
    dp = confine(d)
    if not dp.is_dir():
        raise FileNotFoundError(d)
    rows = []
    for f in sorted(dp.iterdir()):
        if f.name.startswith(".") or f.is_dir():
            continue
        st = f.stat()
        r = {"name": f.name, "path": f"{d}/{f.name}", "kind": f.suffix.lstrip(".") or "file", "size": st.st_size,
             "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))}
        if f.suffix == ".sas":
            sig = signature(r["path"])
            if sig:
                r["shapes"] = sum(1 for x in sig if "<-" not in x); r["edges"] = sum(1 for x in sig if "<-" in x)
            rec = sorted((BENCH / f.stem).glob("*/match.txt")) if (BENCH / f.stem).is_dir() else []
            if rec:
                verdicts = [x.read_text().splitlines()[0] for x in rec]
                r["bench"] = f"{sum(v in ('match', 'match-warn') for v in verdicts)}/{len(verdicts)} blocks match"
        if f.suffix == ".html":
            r["iframe"] = st.st_size <= IFRAME_MAX
        if f.suffix == ".csv":
            with open(f, newline="") as fh:
                r["rows"] = max(0, sum(1 for _ in fh) - 1)
        rows.append(r)
    subdirs = sorted(x.name for x in dp.iterdir() if x.is_dir() and not x.name.startswith("."))
    return {"dir": d, "files": rows, "subdirs": subdirs, "total_bytes": sum(r["size"] for r in rows), "links": folder_links(rows)}


def folder_links(rows):
    """exp_42 2026-09-08: how the files of one folder are linked, for the folder page's file tree and file graph.
    flow    — B reads a table that A writes and B does not write itself (via = the tables)
    subset  — A's lineage rules are all inside B's (a part of the full program); only the smallest such B is kept
    derived — a non-SAS file whose name starts with a SAS file's stem (its PySpark, node/4, notebook ...)"""
    sigs = {}
    for r in rows:
        if r["kind"] == "sas":
            sig = signature(r["path"]) or set()
            edges = [x.split("<-") for x in sig if "<-" in x]
            r["writes"] = sorted({o for o, _ in edges})
            r["reads"] = sorted({i for _, i in edges} - set(r["writes"]))
            sigs[r["name"]] = sig
    links = []
    sas = [r for r in rows if r["kind"] == "sas"]
    for b in sas:
        for a in sas:
            if a is b:
                continue
            via = sorted(set(b["reads"]) & set(a["writes"]))
            if via:
                links.append({"from": a["name"], "to": b["name"], "kind": "flow", "via": via})
    for a in sas:
        supers = [b for b in sas if b is not a and len(sigs[a["name"]]) < len(sigs[b["name"]]) and sigs[a["name"]] <= sigs[b["name"]]]
        if supers:
            b = min(supers, key=lambda x: len(sigs[x["name"]]))
            links.append({"from": b["name"], "to": a["name"], "kind": "subset", "via": [f"{len(sigs[a['name']])} of {len(sigs[b['name']])} rules"]})
    # same rules, other data (the quarter parts of one full program): the canonical one is the file named *full*, else the shortest name
    groups = {}
    for a in sas:
        groups.setdefault(frozenset(sigs[a["name"]]), []).append(a)
    for sig, members in groups.items():
        if len(members) < 2 or not sig:
            continue
        canon = min(members, key=lambda r: (0 if "full" in r["name"] else 1, len(r["name"]), r["name"]))
        for a in members:
            if a is not canon:
                links.append({"from": canon["name"], "to": a["name"], "kind": "same", "via": [f"same {len(sig)} rules, other data"]})
    stems = sorted(((Path(r["name"]).stem, r["name"]) for r in sas), key=lambda x: -len(x[0]))
    for r in rows:
        if r["kind"] == "sas":
            continue
        for stem, name in stems:
            if Path(r["name"]).name.startswith(stem):
                links.append({"from": name, "to": r["name"], "kind": "derived", "via": []})
                break
    return links


def save_buffer(path, text):
    """Save an edited buffer as a copy under out/bench/buffers/ (the repo file itself is never overwritten)."""
    confine(path)
    if text is None:
        raise ValueError("no text")
    BUFFERS.mkdir(parents=True, exist_ok=True)
    dest = BUFFERS / path.replace("/", "__")
    dest.write_text(text)
    return {"path": path, "saved_as": str(dest.relative_to(ROOT)), "bytes": len(text.encode())}


def saved_buffer(path):
    dest = BUFFERS / path.replace("/", "__")
    return {"path": path, "text": dest.read_text(errors="replace"), "saved_as": str(dest.relative_to(ROOT))} if dest.exists() else {"path": path, "text": None}


# ---------------------------------------------------------------- lineage facts
def _split_args(s):
    """top-level comma split of a Prolog argument list, quotes and brackets respected"""
    out, depth, q, cur = [], 0, None, ""
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = None
        elif ch in "'\"":
            q = ch; cur += ch
        elif ch in "[(":
            depth += 1; cur += ch
        elif ch in "])":
            depth -= 1; cur += ch
        elif ch == "," and depth == 0:
            out.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return [a.strip("'") for a in out]


def parse_facts(text):
    facts = {"schema": [], "ds_lineage": [], "col_lineage": [], "ctl_lineage": []}
    for line in text.splitlines():
        m = re.match(r"^(\w+)\((.*)\)\.\s*$", line.strip())
        if not m or m.group(1) not in facts:
            continue
        args = _split_args(m.group(2))
        if m.group(1) == "schema":
            cols = _split_args(args[1].strip("[]")) if len(args) > 1 else []
            facts["schema"].append([args[0], cols])
        else:
            facts["ds_lineage" if m.group(1) == "ds_lineage" else m.group(1)].append(args)
    return facts


def lineage(stem):
    if stem not in PROGRAMS:
        raise KeyError(f"program not open: {stem}")
    return PROGRAMS[stem]["lineage"]


# ---------------------------------------------------------------- open a program
SECTION = re.compile(r"^# ---- (\S+)\s+\((.+?), SAS lines (\d+)-(\d+)\) -+$")


def _py_sections(pretty):
    """The readable PySpark, split at its '# ---- name (kind, SAS lines a-b)' headers."""
    secs, cur = [], None
    for line in pretty.splitlines():
        m = SECTION.match(line)
        if m:
            cur = {"name": m.group(1), "kind": m.group(2), "l0": int(m.group(3)), "l1": int(m.group(4)), "lines": []}
            secs.append(cur)
        elif line.startswith("# ---- every dataset"):
            cur = None
        elif cur is not None:
            cur["lines"].append(line)
    for s in secs:
        body = [l for l in s["lines"] if not l.startswith("#   ")]          # drop the echoed SAS, keep WARNING lines
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        s["py"] = "\n".join(body)
        s["warn"] = next((l.lstrip("# ").strip() for l in s["lines"] if "WARNING" in l or "LINEAGEQ CHECK" in l), "")
    return secs


def open_program(path=None, sas=None, stem=None):
    from server.convert_api import convert
    if path:
        p = confine(path)
        sas = p.read_text()
        stem = stem or p.stem
        note_recent(path)
    if not sas or not sas.strip():
        raise ValueError("no SAS text")
    stem = stem or "paste_" + hashlib.sha1(sas.encode()).hexdigest()[:8]
    with _lock:
        res = convert(sas, run=False, stem=stem)
    work = ROOT / "out/api" / stem
    node4_json = work / "ir" / f"{stem}.node4.json"
    corpus_sas = work / "corpus" / f"{stem}.sas"
    out = {"stem": stem, "path": path, "ok": res["ok"], "errors": res["errors"], "blocks": [], "pyspark_pretty": res.get("pyspark_pretty", ""),
           "receipts": {k: res.get(k) for k in ["statements", "folded", "roundtrip", "source_match", "node4_same", "pyspark_same", "pyspark_pretty_same", "rust_us"]}}
    if not node4_json.exists():
        return out
    nodes = json.loads(node4_json.read_text())
    # lineage from the Rust engine (Prolog's is identical, loop 2)
    lin_dir = work / "lineage"; lin_dir.mkdir(exist_ok=True)
    rc, o, e = sh([RUST, "lineage", "out/spec/sas.json", corpus_sas, lin_dir / "sas.rust.pl"])
    facts = parse_facts((lin_dir / "sas.rust.pl").read_text()) if (lin_dir / "sas.rust.pl").exists() else parse_facts("")
    out["lineage"] = facts
    # blocks: group node/4 by block id, take the SAS lines the trace names
    src = sas.splitlines()
    by_block = {}
    for n in nodes:
        b = by_block.setdefault(n["block"], {"id": n["block"], "terms": [], "l0": 10**9, "l1": 0})
        b["terms"].append(n["term"])
        b["l0"] = min(b["l0"], n["trace"]["l0"]); b["l1"] = max(b["l1"], n["trace"]["l1"])
    secs = _py_sections(out["pyspark_pretty"])
    makers = {o_: i_ for o_, i_ in facts["ds_lineage"]}
    for bid in sorted(by_block, key=lambda k: int(k.split("_")[1])):
        b = by_block[bid]
        sec = next((s for s in secs if not (s["l1"] < b["l0"] or s["l0"] > b["l1"])), None)
        head = b["terms"][0].split("(")[0]
        kind = {"libname": "LIBNAME", "data": "DATA step", "proc_sql": "PROC SQL", "proc": "PROC"}.get(head, head.upper())
        if sec:
            kind = sec["kind"]
        name = sec["name"] if sec else head
        writes = name if sec and sec["kind"] != "LIBNAME" else None
        reads = sorted({i_ for o_, i_ in facts["ds_lineage"] if o_ == writes} | {i_ for o_, i_, _c in facts["ctl_lineage"] if o_ == writes}) if writes else []
        if not writes:   # exp_42 2026-09-08: a block that makes no table (PROC PRINT ...) still reads the ds(...) it names
            reads = sorted({f"{m.group(1)}.{m.group(2)}" for t in b["terms"] for m in re.finditer(r"ds\((\w+),(\w+)\)", t)})
        out["blocks"].append({"id": bid, "n": int(bid.split("_")[1]), "kind": kind, "name": name, "lines": f"{b['l0']}-{b['l1']}",
                              "sas": "\n".join(src[b["l0"] - 1:b["l1"]]), "py": sec["py"] if sec else "", "warn": sec["warn"] if sec else "",
                              "reads": reads, "writes": writes, "terms": b["terms"]})
    del makers
    PROGRAMS[stem] = out
    return out


# ---------------------------------------------------------------- run one block on both sides
def _csv_rows(p):
    if not Path(p).exists():
        return None
    with open(p, newline="") as fh:
        rows = list(csv.reader(fh))
    return rows


def _ensure_blocks(stem):
    """Z3 inputs + block programs for every block of the program, once."""
    work = ROOT / "out/api" / stem
    bdir = work / "blocks"
    if (bdir / "manifest.json").exists():
        return bdir, json.loads((bdir / "manifest.json").read_text()), ""
    node4_json = work / "ir" / f"{stem}.node4.json"
    log = []
    rc, o, e = sh([PY, "loops/gen_block_testdata.py", stem, node4_json, bdir]); log.append(o + e)
    # the plain PySpark body is what the PySpark pyDSL folds (as the studio does)
    py_plain = work / f"{stem}_ravi_prolog.py"
    body_dir = work / "pyspark_corpus"; body_dir.mkdir(exist_ok=True)
    lines = py_plain.read_text().splitlines(keepends=True)
    last = max(i for i, l in enumerate(lines) if l.startswith("# ====="))
    job = body_dir / f"{stem}.py"; job.write_text("".join(lines[last + 1:]).lstrip("\n"))
    rc, o, e = sh([RUST, "block-programs", "out/spec/pyspark.json", job, "codegen/sas_runtime_preamble.py", bdir]); log.append(o + e)
    manifest = json.loads((bdir / "manifest.json").read_text()) if (bdir / "manifest.json").exists() else []
    return bdir, manifest, "\n".join(log)


def run_block(stem, block, engine="rust", session_id=None):
    if stem not in PROGRAMS:
        raise KeyError(f"program not open: {stem}")
    prog = PROGRAMS[stem]
    binfo = next((b for b in prog["blocks"] if b["id"] == block), None)
    if binfo is None:
        raise KeyError(f"no block {block}")
    res = {"stem": stem, "block": block, "engine": engine, "left": None, "right": None, "match": None, "tables": {}, "warn": binfo["warn"], "log": ""}
    if not binfo["writes"]:
        res["match"] = "no table"
        return res
    work = ROOT / "out/api" / stem
    bdir, manifest, log = _ensure_blocks(stem)
    entry = next((e for e in manifest if e["block"] == block), None)
    if entry is None:
        res["match"] = "no inputs"; res["log"] = log + f"\nmanifest has no block {block} (it creates nothing to test)"
        return res
    d = bdir / block
    corpus_sas = work / "corpus" / f"{stem}.sas"
    node4_pl = work / "ir" / f"{stem}.node4.pl"
    # left: the executable node/4
    t0 = time.time()
    if engine == "prolog":
        rc, o, e = sh(["swipl", "-q", "-s", "codegen/sas_interp.pl", "-g", "main", "--", node4_pl, d / "in", d / "prolog", block]); left_dir = d / "prolog"
    else:
        rc, o, e = sh([RUST, "interp", "out/spec/sas.json", corpus_sas, d / "in", d / "rust", block]); left_dir = d / "rust"
    res["left"] = {"ms": round((time.time() - t0) * 1000, 1), "log": (o + e).strip()[-2000:], "rc": rc}
    # right: the block's own PySpark program, in the session kernel or locally
    progs = sorted(d.glob("block_*_rust.py"))
    if not progs:
        res["match"] = "no program"; res["log"] = log; return res
    code = progs[0].read_text()
    out_dir = d / "spark"
    t0 = time.time()
    sess = SESSIONS.get(session_id) if session_id else None
    if sess:
        # a kernel keeps ONE Spark session across cells: the program's spark.stop() would kill the JVM gateway for the next cell
        kcode = re.sub(r"^spark\.stop\(\)\s*$", "pass  # bench: the kernel keeps its Spark session", code, flags=re.M)
        rc, o, e = sess.execute(f"import os\nos.environ.setdefault('JAVA_HOME', {JAVA_HOME!r})\nos.environ['LINEAGEQ_OUT'] = {str(out_dir)!r}\nos.chdir({str(ROOT)!r})\n" + kcode)
        where = f"kernel {sess.kernel[:8]}"
    else:
        env = dict(os.environ, JAVA_HOME=JAVA_HOME, LINEAGEQ_OUT=str(out_dir))
        rc, o, e = sh([PY, progs[0]], env=env)
        where = "local python"
    quiet = "\n".join(l for l in (o + e).splitlines() if not re.search(r"WARN|Stage \d|setLogLevel|log4j", l))
    res["right"] = {"ms": round((time.time() - t0) * 1000, 1), "log": quiet.strip()[-2000:], "rc": rc, "where": where}
    # judge every table the block creates
    verdicts = []
    for t in entry["creates"]:
        L, R = _csv_rows(left_dir / f"{t}.csv"), _csv_rows(out_dir / f"{t}.csv")
        tab = {"left": L, "right": R}
        if L is None or R is None:
            tab["verdict"] = "missing"; tab["missing"] = "left" if L is None else "right"
        else:
            v, n, samples = compare_rows(L[1:], R[1:])
            tab["verdict"] = "match" if v == "PASS" else "differs"; tab["n_mismatch"] = n; tab["samples"] = samples
            if v == "PASS" and (len(L) <= 1 or binfo["warn"]):
                tab["verdict"] = "match-warn"
        res["tables"][t] = tab
        verdicts.append(tab["verdict"])
    res["match"] = "differs" if "differs" in verdicts else "missing" if "missing" in verdicts else "match-warn" if "match-warn" in verdicts else "match"
    res["log"] = log
    # receipts
    rdir = BENCH / stem / block; rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "match.txt").write_text(f"{res['match']}\n" + "\n".join(f"{t} {v['verdict']}" for t, v in res["tables"].items()) + "\n")
    with open(BENCH / "timings.csv", "a") as fh:
        fh.write(f"bench,{engine},{stem} {block} left,{res['left']['ms']}\nbench,{where.split()[0]},{stem} {block} right,{res['right']['ms']}\n")
    return res


# ---------------------------------------------------------------- similar programs
SAS_DIRS = ["../../corpus/team_finance/sas/raw"]   # 2026-09-09: one corpus, see docs/superpowers/specs/2026-09-09-team-finance-corpus-design.md
SIG_DIR = BENCH / "sig"


def _shapes(nodes):
    """one shape per block: the head of its first term + its top-level arity, e.g. data/1"""
    first = {}
    for n in nodes:
        first.setdefault(n["block"], n["term"])
    return {t.split("(")[0] + "/" + str(t.count(",")) for t in first.values()}


def _node4_pl_nodes(text):
    """the (block, term) pairs of a node4.pl file, the way the JSON carries them"""
    out = []
    for line in text.splitlines():
        m = re.match(r"^node\('?(\w+)'?,\s*\d+,\s*(.*),\s*trace\(", line)
        if m:
            out.append({"block": m.group(1), "term": m.group(2)})
    return out


def _cached_signature(path):
    """Fold a SAS file the page never opened through the Rust engine once (milliseconds) and keep
    its shapes + edges in out/bench/sig/<stem>.json, refreshed when the file changes."""
    src = ROOT / path
    stem = src.stem
    SIG_DIR.mkdir(parents=True, exist_ok=True)
    cache = SIG_DIR / f"{stem}.json"
    if cache.exists():
        c = json.loads(cache.read_text())
        if c.get("mtime") == src.stat().st_mtime:
            return set(c["sig"])
    work = SIG_DIR / stem; work.mkdir(exist_ok=True)
    sh([RUST, "out/spec/sas.json", src, work])
    sh([RUST, "lineage", "out/spec/sas.json", src, work / "sas.rust.pl"])
    n4 = work / f"{stem}.node4.pl"
    if not n4.exists():
        return None
    shapes = _shapes(_node4_pl_nodes(n4.read_text()))
    lin = work / "sas.rust.pl"
    edges = {f"{o}<-{i}" for o, i in parse_facts(lin.read_text())["ds_lineage"]} if lin.exists() else set()
    sig = shapes | edges
    cache.write_text(json.dumps({"mtime": src.stat().st_mtime, "sig": sorted(sig)}))
    return sig


def signature(stem_or_path):
    """block shapes (term heads) ∪ lineage edges of a program; None when it cannot be folded"""
    if stem_or_path in PROGRAMS:
        p = PROGRAMS[stem_or_path]
        shapes = {t.split("(")[0] + "/" + str(t.count(",")) for b in p["blocks"] for t in b["terms"][:1]}
        edges = {f"{o}<-{i}" for o, i in p["lineage"]["ds_lineage"]}
        return shapes | edges
    path = Path(stem_or_path)
    stem = path.stem
    n4 = ROOT / "out/ir/sas" / f"{stem}.node4.json"
    if n4.exists():
        lin = ROOT / "out/loops/lineage" / f"{stem}.sas.rust.pl"
        shapes = _shapes(json.loads(n4.read_text()))
        edges = {f"{o}<-{i}" for o, i in parse_facts(lin.read_text())["ds_lineage"]} if lin.exists() else set()
        return shapes | edges
    if path.suffix == ".sas" and (ROOT / path).is_file():
        return _cached_signature(str(path))
    for d in SAS_DIRS:                       # a bare stem: the first SAS folder that holds it
        if (ROOT / d / f"{stem}.sas").is_file():
            return _cached_signature(f"{d}/{stem}.sas")
    return None


def similar(stem):
    mine = signature(stem)
    if mine is None:
        return []
    me = PROGRAMS.get(stem, {}).get("path")
    out = []
    for d in SAS_DIRS:
        for f in sorted((ROOT / d).glob("*.sas")):
            rel = f"{d}/{f.name}"
            if rel == me or (me is None and f.stem == stem):
                continue
            sig = signature(rel)
            if sig is None:
                continue
            j = len(mine & sig) / max(1, len(mine | sig))
            shared_edges = sum(1 for x in mine & sig if "<-" in x); all_edges = sum(1 for x in mine | sig if "<-" in x)
            out.append({"path": rel, "score": round(j, 2), "why": f"{shared_edges}/{all_edges} lineage edges shared, {len(mine & sig)}/{len(mine | sig)} features"})
    return sorted(out, key=lambda x: (-x["score"], x["path"]))


# ---------------------------------------------------------------- the SAS listing (pasted; the real SAS output the owner runs on SAS OnDemand)
LISTINGS = {}          # stem -> {"text", "tables": {name: (cols, rows)}, "source"}
FILE_CSV_DIR = ROOT / "out/pyspark_ravi"   # the file-level Spark run of run_all.sh step 5, the side a SAS listing is comparable with


def parse_listing(text):
    """PROC PRINT output: a title line naming the table, an 'Obs ...' header, rows until a blank line.
    Same shape as compare_sas_vs_pyspark.parse_sas_listing but any name-looking title is accepted."""
    out, lines = {}, text.splitlines()
    is_name = lambda t: re.fullmatch(r"[a-z_][a-z0-9_.]*", t) is not None
    i = 0
    while i < len(lines):
        title = lines[i].strip().lower()
        if is_name(title):
            j = i + 1
            while j < len(lines) and not lines[j].strip().lower().startswith("obs"):
                if lines[j].strip() and is_name(lines[j].strip().lower()):
                    break
                j += 1
            if j >= len(lines) or not lines[j].strip().lower().startswith("obs"):
                i += 1; continue
            cols = [c.lower() for c in lines[j].split()[1:]]
            rows = []
            j += 1
            while j < len(lines) and lines[j].strip():
                parts = lines[j].split()
                if parts and parts[0].isdigit():
                    rows.append(parts[1:])
                j += 1
            out[title] = (cols, rows)
            i = j
        else:
            i += 1
    return out


def set_listing(stem, text=None, path=None):
    """Store a listing for a program (pasted text or a file under the repo) and judge it."""
    if path:
        text = confine(path).read_text(errors="replace"); source = path
    else:
        source = "pasted"
    if not text or not text.strip():
        raise ValueError("no listing text")
    tables = parse_listing(text)
    if not tables:
        raise ValueError("no PROC PRINT tables found (expected: a title line, an 'Obs ...' header, then rows)")
    LISTINGS[stem] = {"text": text, "tables": tables, "source": source}
    BENCH.mkdir(parents=True, exist_ok=True)
    (BENCH / f"{stem}.listing.txt").write_text(text)
    return listing_verdicts(stem)


def listing_verdicts(stem):
    """Per table: match / differs / missing against the file-level Spark CSVs; 'awaited' when no listing is loaded."""
    L = LISTINGS.get(stem)
    if not L:
        return {"stem": stem, "loaded": False, "tables": {}}
    out = {"stem": stem, "loaded": True, "source": L["source"], "tables": {}}
    for name, (cols, rows) in L["tables"].items():
        short = name.split(".")[-1]
        csv_path = next((p for p in [FILE_CSV_DIR / f"{name}.csv", FILE_CSV_DIR / f"sales.{short}.csv"] + sorted(FILE_CSV_DIR.glob(f"*.{short}.csv")) if p.exists()), None)
        if csv_path is None:
            out["tables"][short] = {"verdict": "missing", "why": "no file-level Spark CSV (run_all.sh step 5)", "sas_rows": len(rows)}
            continue
        py = _csv_rows(csv_path)
        pcols = [c.lower() for c in py[0]]
        if pcols != cols:
            out["tables"][short] = {"verdict": "differs", "why": f"columns differ: sas={cols} pyspark={pcols}", "sas_rows": len(rows), "py_rows": len(py) - 1}
            continue
        v, n, samples = compare_rows(rows, py[1:])
        out["tables"][short] = {"verdict": "match" if v == "PASS" else "differs", "n_mismatch": n, "samples": samples,
                                "sas_rows": len(rows), "py_rows": len(py) - 1, "csv": str(csv_path.relative_to(ROOT))}
    return out


# ---------------------------------------------------------------- the allow-listed terminal
def _lev(a, b):
    d = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    return d[len(a)][len(b)]


def term(cmd, args, stem=None, block=None):
    cmd = (cmd or "").strip()
    args = (args or "").strip()
    known = ["run_all", "run_loops", "convert", "fold", "diff", "compare", "ls"]
    if cmd not in known:
        best = sorted(((0 if k.startswith(cmd) else _lev(cmd.lower(), k), k) for k in known))[0] if cmd else None
        return {"refused": True, "lines": [f"not allowed: {cmd}"], "suggestion": best[1] if best and best[0] <= 2 else None, "known": known}
    lines, links = [], []
    if cmd == "ls":
        for d in SAS_DIRS:
            lines += [f"{d}/{f.name}" for f in sorted((ROOT / d).glob("*.sas"))]
    elif cmd == "run_all":
        rc, o, e = sh(["./run_all.sh"], timeout=900); lines = (o + e).splitlines()[-40:]
    elif cmd == "run_loops":
        rc, o, e = sh(["./loops/run_loops.sh"], timeout=900); lines = (o + e).splitlines()[-40:]
    elif cmd == "convert":
        path = args or "../../corpus/team_finance/sas/raw/09_customer_summary.sas"
        p = open_program(path=path)
        r = p["receipts"]
        lines = [f"$ open {path}", f"statements {r['statements']} · folded {r['folded']} · roundtrip {r['roundtrip']} · source_match {r['source_match']}",
                 f"node4_same {r['node4_same']} · pyspark_same {r['pyspark_same']} · pretty_same {r['pyspark_pretty_same']}", f"rust_us {r['rust_us']}"]
    elif cmd in ("fold", "diff"):
        if stem not in PROGRAMS:
            return {"lines": ["open a program first"], "links": []}
        b = args or block
        blk = next((x for x in PROGRAMS[stem]["blocks"] if x["id"] == b or str(x["n"]) == str(b)), None)
        if blk is None:
            return {"lines": [f"no block {b}"], "links": []}
        if cmd == "fold":
            lines = [f"$ fold block {blk['id']}  ({blk['name']}, SAS L{blk['lines']})"] + [f"node({blk['id']}, {k + 1}, {t}, trace({blk['lines']}))" for k, t in enumerate(blk["terms"])] + ["printed back == source (bytes): see receipts"]
        else:
            r = run_block(stem, blk["id"], "rust")
            lines = [f"$ diff block {blk['id']}  rust interp vs spark"]
            for t, v in r["tables"].items():
                nrows = (len(v["left"]) - 1) if v["left"] else 0
                lines.append(f"{t}  {v['verdict']}  ({nrows} rows)"); links.append({"table": t, "block": blk["id"]})
            if not r["tables"]:
                lines.append(r["match"])
    elif cmd == "compare":
        # exp_42 2026-09-08: a path compares that file; no path compares the listing pasted in the DataMatch tab
        if args:
            v = set_listing(stem or "paste", path=args)
        elif stem in LISTINGS:
            v = listing_verdicts(stem)
        else:
            return {"lines": ["no SAS listing yet: run corpus/team_finance/sas/raw/09_customer_summary.sas in SAS OnDemand, then paste the listing in the DataMatch tab or: compare <listing.txt>"], "links": []}
        lines = [f"$ compare {v['source']}  (SAS listing vs file-level Spark CSVs, {FILE_CSV_DIR.relative_to(ROOT)})"]
        for t, r in v["tables"].items():
            lines.append(f"{t}  {r['verdict']}  " + (r.get("why") or f"sas {r['sas_rows']} rows / pyspark {r.get('py_rows')} rows" + (f", {r['n_mismatch']} differ" if r.get("n_mismatch") else "")))
        n_ok = sum(1 for r in v["tables"].values() if r["verdict"] == "match")
        lines.append(f"{n_ok}/{len(v['tables'])} tables match")
    return {"lines": lines, "links": links}


# ---------------------------------------------------------------- Jupyter sessions (through the server; the page never sees the token)
class JupyterSession:
    def __init__(self, url, name):
        import requests
        m = re.match(r"^(https?://[^/]+)(/[^?]*)?(?:\?.*token=([A-Za-z0-9]+))?", url.strip())
        if not m:
            raise ValueError("not a Jupyter URL (expected http://host:port/...?token=...)")
        self.base = m.group(1) + (m.group(2) or "").split("/lab")[0].split("/tree")[0].rstrip("/")
        self.token = m.group(3) or ""
        self.id = uuid.uuid4().hex[:8]
        self.name = name
        self.url = url
        self.busy = False
        self.lock = threading.Lock()
        self.error = ""
        try:
            r = requests.post(f"{self.base}/api/kernels", params={"token": self.token}, json={"name": "python3"}, timeout=10)
        except requests.RequestException as e:
            raise ValueError(f"cannot reach {self.base}: {type(e).__name__}")
        if r.status_code >= 300:
            raise ValueError(f"kernel start refused by {self.base}: HTTP {r.status_code} {r.text[:120]}")
        self.kernel = r.json()["id"]

    def execute(self, code, timeout=600):
        import websocket
        with self.lock:
            self.busy = True
            try:
                ws_url = self.base.replace("http", "ws", 1) + f"/api/kernels/{self.kernel}/channels?token={self.token}"
                ws = websocket.create_connection(ws_url, timeout=timeout)
                msg_id = uuid.uuid4().hex
                hdr = {"msg_id": msg_id, "username": "bench", "session": self.id, "msg_type": "execute_request", "version": "5.3", "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                ws.send(json.dumps({"header": hdr, "parent_header": {}, "metadata": {}, "channel": "shell",
                                    "content": {"code": code, "silent": False, "store_history": False, "allow_stdin": False, "stop_on_error": True}}))
                out, err, rc, t_end = [], [], 0, time.time() + timeout
                while time.time() < t_end:
                    m = json.loads(ws.recv())
                    if m.get("parent_header", {}).get("msg_id") != msg_id:
                        continue
                    t = m["msg_type"]; c = m.get("content", {})
                    if t == "stream":
                        (out if c.get("name") == "stdout" else err).append(c.get("text", ""))
                    elif t == "error":
                        err.append("\n".join(c.get("traceback", []))); rc = 1
                    elif t == "status" and c.get("execution_state") == "idle":
                        break
                ws.close()
                return rc, "".join(out), re.sub(r"\x1b\[[0-9;]*m", "", "".join(err))
            except Exception as e:
                self.error = repr(e)
                return 1, "", f"session {self.name}: {e!r}"
            finally:
                self.busy = False

    def close(self):
        import requests
        try:
            requests.delete(f"{self.base}/api/kernels/{self.kernel}", params={"token": self.token}, timeout=5)
        except Exception:
            pass

    def info(self):
        return {"id": self.id, "name": self.name, "url": re.sub(r"token=[^&]+", "token=…", self.url), "kernel": self.kernel, "busy": self.busy, "error": self.error}


SESSIONS = {}


def attach(url, name=None):
    s = JupyterSession(url, name or f"session {len(SESSIONS) + 1}")
    SESSIONS[s.id] = s
    return s.info()


def list_sessions():
    return [s.info() for s in SESSIONS.values()]


def detach(sid):
    s = SESSIONS.pop(sid, None)
    if s:
        s.close()
    return {"ok": s is not None}


def exec_code(code, session_id=None):
    """A user-made # %% cell: run it in the attached kernel, or locally when none is attached."""
    t0 = time.time()
    sess = SESSIONS.get(session_id) if session_id else None
    if sess:
        rc, o, e = sess.execute(code); where = f"kernel {sess.kernel[:8]}"
    else:
        env = dict(os.environ, JAVA_HOME=JAVA_HOME)
        rc, o, e = sh([PY, "-c", code], env=env, timeout=600); where = "local python"
    quiet = "\n".join(l for l in (o + e).splitlines() if not re.search(r"WARN|Stage \d|setLogLevel|log4j", l))
    return {"rc": rc, "out": quiet.strip()[-4000:], "ms": round((time.time() - t0) * 1000, 1), "where": where}
