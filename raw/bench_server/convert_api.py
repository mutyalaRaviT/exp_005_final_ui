"""server/convert_api.py — the exp_42 converter as a local HTTP API + page.

Why: paste any SAS, get back what the pipeline makes of it — tokens, node/4
from the Prolog DCG and from the Rust engine, the SAS printed back from node/4,
the generated PySpark from both engines, whether the two agree, and (on
request) the rows PySpark produces. Same steps as run_all.sh, one request each.

Run:   .venv/bin/python server/convert_api.py [--port 8042]
Open:  http://localhost:8042/

API
  POST /api/convert     body {"sas": "...", "run": false}
        -> {"ok", "stem", "statements", "folded", "roundtrip", "errors": [...],
            "node4_prolog", "node4_rust", "node4_same",
            "printed_sas" (rebuilt from node/4, must equal the input), "source_match", "printed_canonical",
            "pyspark_pretty" (the readable program; what the page shows), "pyspark_pretty_same",
            "pyspark_prolog", "pyspark_rust", "pyspark_same" (the plain printer, kept as the proof),
            "rust_us", "listing" (when run=true), "log"}
  GET  /api/example     -> {"sas": <raw/test_vishnu.sas>}
  GET  /api/spec        -> the pyDSL spec as JSON (out/spec/sas.json)
  GET  /api/health      -> {"ok": true}
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from server import bench_api as bench  # noqa: E402  (exp_42 bench, 2026-09-07)
PY = ROOT / ".venv/bin/python"
RUST = ROOT / "rust_engine/target/release/lineageq_sas"
JAVA_HOME = os.environ.get("JAVA_HOME_17", "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")


def sh(cmd, cwd=ROOT, env=None, timeout=600):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, p.stdout, p.stderr


def convert(sas_text, run=False, stem=None):
    stem = stem or "api_" + uuid.uuid4().hex[:8]          # exp_42 bench 2026-09-07: a stable stem per opened file
    work = ROOT / "out/api" / stem
    corpus = work / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    (corpus / f"{stem}.sas").write_text(sas_text)
    log = []
    res = {"ok": False, "stem": stem, "errors": []}
    tokens_json = ROOT / "out/tokens/sas" / f"{stem}.tokens.json"
    try:
        # 1 tokenise (writes out/tokens/sas/<stem>.tokens.json)
        rc, out, err = sh([str(PY), "-m", "pipeline.run_tokenise", "sas", "--dir", str(corpus)])
        log.append(out + err)
        if rc != 0:
            res["errors"].append("tokenise failed:\n" + out + err)
            return res
        # 2 Prolog fold + round trip -> node/4
        rc, out, err = sh([str(PY), "-m", "pipeline.run_fold", "sas", "--file", stem,
                           "--out-dir", str(work / "ir"), "--work-dir", str(work / "work")])
        log.append(out + err)
        m = re.search(rf"{stem}\s+(\d+)/(\d+)\s+(\d+)/(\d+)", out)
        if m:
            res["folded"], res["statements"], res["roundtrip"] = int(m.group(1)), int(m.group(2)), int(m.group(3))
        res["errors"] += [l.strip() for l in out.splitlines() if l.strip().startswith("seq ")]
        node4_pl = work / "ir" / f"{stem}.node4.pl"
        if not node4_pl.exists():
            res["errors"].append("fold produced no node/4:\n" + out + err)
            return res
        res["node4_prolog"] = "\n".join(l for l in node4_pl.read_text().splitlines() if l.startswith("node("))
        # 3 Prolog codegen
        py_prolog = work / f"{stem}_ravi_prolog.py"
        rc, out, err = sh(["swipl", "-q", "-s", "codegen/sas_pyspark.pl", "-g", "main", "--",
                           str(node4_pl), "codegen/sas_runtime_preamble.py", str(py_prolog)])
        log.append(out + err)
        res["pyspark_prolog"] = py_prolog.read_text() if py_prolog.exists() else ""
        if rc != 0:
            res["errors"].append("prolog codegen: " + err.strip())
        # 4 Rust: fold + unfold + node/4 + pyspark
        rc, out, err = sh([str(RUST), "out/spec/sas.json", str(corpus / f"{stem}.sas"), str(work / "rust"),
                           "codegen/sas_runtime_preamble.py", "codegen/sas_runtime_pretty.py"])
        log.append(out + err)
        m = re.search(r"\((\d+) us total\)", out)
        res["rust_us"] = int(m.group(1)) if m else None
        res["rust_summary"] = out.strip()
        if err.strip():
            res["errors"] += ["rust: " + l for l in err.strip().splitlines()]
        rust_node4 = work / "rust" / f"{stem}.node4.pl"
        res["node4_rust"] = rust_node4.read_text().strip() if rust_node4.exists() else ""
        printed = work / "rust" / f"{stem}.printed.sas"
        res["printed_canonical"] = printed.read_text() if printed.exists() else ""
        rebuilt = work / "rust" / f"{stem}.rebuilt.sas"
        res["printed_sas"] = rebuilt.read_text() if rebuilt.exists() else ""
        res["source_match"] = res["printed_sas"] == sas_text
        py_rust = work / "rust" / f"{stem}_ravi_rust.py"
        res["pyspark_rust"] = py_rust.read_text() if py_rust.exists() else ""
        # the readable version: Prolog printer vs Rust printer
        pretty_prolog = work / f"{stem}_pretty_prolog.py"
        rc, out, err = sh(["swipl", "-q", "-s", "codegen/sas_pyspark_pretty.pl", "-g", "main", "--",
                           str(node4_pl), "codegen/sas_runtime_pretty.py", str(pretty_prolog)])
        log.append(out + err)
        res["pyspark_pretty"] = pretty_prolog.read_text() if pretty_prolog.exists() else ""
        pretty_rust = work / "rust" / f"{stem}_pretty_rust.py"
        res["pyspark_pretty_same"] = pretty_rust.exists() and pretty_rust.read_text() == res["pyspark_pretty"] and bool(res["pyspark_pretty"])
        # node/4 texts name the source path; compare with the path stripped
        strip = lambda s: re.sub(r"trace\('[^']*',", "trace(_,", s)
        res["node4_same"] = strip(res["node4_prolog"]) == strip(res["node4_rust"])
        res["pyspark_same"] = res["pyspark_prolog"] == res["pyspark_rust"] and bool(res["pyspark_prolog"])
        # 5 run the PySpark
        if run and res["pyspark_pretty"]:
            env = dict(os.environ, JAVA_HOME=JAVA_HOME, LINEAGEQ_OUT=str(work / "pyspark_out"))
            t0 = time.time()
            rc, out, err = sh([str(PY), str(pretty_prolog)], env=env)
            listing = "\n".join(l for l in out.splitlines() if not re.search(r"WARN|Stage \d|setLogLevel", l))
            res["listing"] = listing.strip()
            res["run_seconds"] = round(time.time() - t0, 1)
            if rc != 0:
                res["errors"].append("pyspark run failed:\n" + "\n".join(err.splitlines()[-15:]))
        res["ok"] = not res["errors"]
        return res
    finally:
        res["log"] = "\n".join(log)
        if tokens_json.exists():
            tokens_json.unlink()   # keep run_all.sh's corpus clean


def read_csv_dir(d):
    """{lib.name: csv text} for every CSV in a directory (the executors' outputs)"""
    d = Path(d)
    if not d.is_dir():
        return None
    return {f.name[:-4]: f.read_text() for f in sorted(d.glob("*.csv"))}


def studio(sas_text, run=False, blocks=False, prolog_pyspark=False):
    """exp_42 studio (2026-09-07): every intermediate step of the four loops for ONE program.
    Returns the convert() result plus tokens, the PySpark node/4, the lineage facts from
    both engines, the file-level tables from the Prolog and Rust interpreters (and Spark
    when run=True), and the block-level tables per step (Spark when blocks=True)."""
    t = {}
    t0 = time.time()
    res = convert(sas_text, run=run)
    t["convert"] = round((time.time() - t0) * 1000)
    stem = res["stem"]
    work = ROOT / "out/api" / stem
    corpus_sas = work / "corpus" / f"{stem}.sas"
    node4_pl = work / "ir" / f"{stem}.node4.pl"
    node4_json = work / "ir" / f"{stem}.node4.json"
    log = [res.get("log", "")]
    try:
        # tokens (run_tokenise wrote them, convert() deleted the file: tokenise again in-process)
        import importlib
        sys.path.insert(0, str(ROOT))
        from pipeline.tokeniser import tokenise
        spec = importlib.import_module("pipeline.specs.sas").LANG
        toks = tokenise(spec, sas_text)
        res["tokens"] = [{"kind": x["kind"], "text": x["text"], "line": x["line"]} for x in toks if x["kind"] != "eos"]
        res["lossless"] = "".join(x["text"] for x in toks) == sas_text
        if not node4_pl.exists():
            return res
        # loop 2: PySpark body -> its own pyDSL (Rust always; Prolog on request, it is slow) -> lineage x4
        t0 = time.time()
        py_plain = work / f"{stem}_ravi_prolog.py"
        body_dir = work / "pyspark_corpus"; body_dir.mkdir(exist_ok=True)
        text = py_plain.read_text(); lines = text.splitlines(keepends=True)
        last = max(i for i, l in enumerate(lines) if l.startswith("# ====="))
        job = body_dir / f"{stem}.py"; job.write_text("".join(lines[last + 1:]).lstrip("\n"))
        rc, out, err = sh([str(RUST), "out/spec/pyspark.json", str(job), str(work / "rust_py")]); log.append(out + err)
        m = re.search(r"folded (\d+)\s+roundtrip (\d+)", out); n = re.search(r"statements (\d+)", out)
        res["pyspark_fold"] = {"statements": int(n.group(1)) if n else None, "folded": int(m.group(1)) if m else None,
                               "roundtrip": int(m.group(2)) if m else None, "engine": "rust"}
        pn = work / "rust_py" / f"{stem}.node4.pl"
        res["pyspark_node4"] = pn.read_text().strip() if pn.exists() else ""
        lin = work / "lineage"; lin.mkdir(exist_ok=True)
        L = {}
        rc, out, err = sh(["swipl", "-q", "-s", "codegen/sas_lineage.pl", "-g", "main", "--", str(node4_pl), str(lin / "sas.prolog.pl")]); log.append(out + err)
        rc, out, err = sh([str(RUST), "lineage", "out/spec/sas.json", str(corpus_sas), str(lin / "sas.rust.pl")]); log.append(out + err)
        rc, out, err = sh([str(RUST), "lineage", "out/spec/pyspark.json", str(job), str(lin / "py.rust.pl")]); log.append(out + err)
        if prolog_pyspark:
            tok_dir = work / "py_tokens"; tok_dir.mkdir(exist_ok=True)
            rc, out, err = sh([str(PY), "-m", "pipeline.run_tokenise", "pyspark", "--dir", str(body_dir)]); log.append(out + err)
            rc, out, err = sh([str(PY), "-m", "pipeline.run_fold", "pyspark", "--file", stem, "--out-dir", str(work / "ir_py"), "--work-dir", str(work / "work_py")]); log.append(out + err)
            pyn = work / "ir_py" / f"{stem}.node4.pl"
            tj = ROOT / "out/tokens/pyspark" / f"{stem}.tokens.json"
            if tj.exists(): tj.unlink()
            if pyn.exists():
                rc, out, err = sh(["swipl", "-q", "-s", "codegen/pyspark_lineage.pl", "-g", "main", "--", str(pyn), str(lin / "py.prolog.pl")]); log.append(out + err)
        for f in sorted(lin.glob("*.pl")):
            L[f.name[:-3]] = f.read_text()
        res["lineage"] = L
        res["lineage_same"] = len(set(L.values())) == 1 and bool(L)
        t["lineage"] = round((time.time() - t0) * 1000)
        # loop 4 at file level: both interpreters (+ Spark tables from convert() when run)
        t0 = time.time()
        rc, out, err = sh(["swipl", "-q", "-s", "codegen/sas_interp.pl", "-g", "main", "--", str(node4_pl), "/nonexistent", str(work / "interp_prolog")]); log.append(out + err)
        t["interp_prolog"] = round((time.time() - t0) * 1000); prolog_log = out
        t0 = time.time()
        rc, out, err = sh([str(RUST), "interp", "out/spec/sas.json", str(corpus_sas), "/nonexistent", str(work / "interp_rust")]); log.append(out + err)
        t["interp_rust"] = round((time.time() - t0) * 1000)
        res["file"] = {"prolog": read_csv_dir(work / "interp_prolog"), "rust": read_csv_dir(work / "interp_rust"),
                       "spark": read_csv_dir(work / "pyspark_out"), "sas_log": prolog_log.strip(), "spark_seconds": res.get("run_seconds")}
        # loop 3 at block level: inputs from Z3 over node/4, both interpreters per block, block programs (Rust printer), Spark on request
        t0 = time.time()
        bdir = work / "blocks"
        rc, out, err = sh([str(PY), "loops/gen_block_testdata.py", stem, str(node4_json), str(bdir)]); log.append(out + err)
        manifest = json.loads((bdir / "manifest.json").read_text()) if (bdir / "manifest.json").exists() else []
        rc, out, err = sh([str(RUST), "block-programs", "out/spec/pyspark.json", str(job), "codegen/sas_runtime_preamble.py", str(bdir)]); log.append(out + err)
        per = {}
        for e in manifest:
            b = e["block"]; d = bdir / b
            rc, out, err = sh(["swipl", "-q", "-s", "codegen/sas_interp.pl", "-g", "main", "--", str(node4_pl), str(d / "in"), str(d / "prolog"), b]); log.append(out + err)
            rc, out2, err = sh([str(RUST), "interp", "out/spec/sas.json", str(corpus_sas), str(d / "in"), str(d / "rust"), b]); log.append(out2 + err)
            progs = sorted(d.glob("block_*_rust.py"))
            if blocks:
                env = dict(os.environ, JAVA_HOME=JAVA_HOME, LINEAGEQ_OUT=str(d / "spark"))
                for pgm in progs:
                    rc, o, er = sh([str(PY), str(pgm)], env=env); log.append(o + er)
            per[b] = {"creates": e["creates"], "inputs": read_csv_dir(d / "in") or {}, "schemas": {f.name[:-12]: json.loads(f.read_text()) for f in (d / "in").glob("*.schema.json")},
                      "conditions": e.get("conditions", []), "prolog": read_csv_dir(d / "prolog") or {}, "rust": read_csv_dir(d / "rust") or {},
                      "spark": read_csv_dir(d / "spark"), "program": "\n".join(pgm.read_text().split("spark = make_spark()", 1)[-1].strip().replace(str(ROOT) + "/", "") for pgm in progs),
                      "sas_log": out.strip()}
        res["blocks"] = per
        t["blocks"] = round((time.time() - t0) * 1000)
        return res
    finally:
        res["timings"] = t
        res["log"] = "\n".join(log)


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    # ---- exp_42 bench (2026-09-07): the workbench page and its endpoints; logic in server/bench_api.py
    def _bench_get(self, path, qs):
        from urllib.parse import parse_qs
        q = {k: v[0] for k, v in parse_qs(qs).items()}
        if path == "/favicon.ico":
            self.send_response(204); self.end_headers(); return True
        if path in ("/bench", "/bench.html"):
            body = (ROOT / "server/bench.html").read_bytes()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return True
        try:
            if path == "/api/files":
                return self._json(200, bench.list_files()) or True
            if path == "/api/file":
                return self._json(200, bench.read_file(q.get("path", ""))) or True
            if path == "/api/lineage":
                return self._json(200, bench.lineage(q.get("stem", ""))) or True
            if path == "/api/similar":
                return self._json(200, bench.similar(q.get("stem", ""))) or True
            if path == "/api/sessions":
                return self._json(200, bench.list_sessions()) or True
            if path == "/api/listing":   # exp_42 2026-09-08: the pasted SAS listing's verdicts
                return self._json(200, bench.listing_verdicts(q.get("stem", ""))) or True
            if path == "/api/folder":    # exp_42 2026-09-08: folder aggregation for the Files dock
                return self._json(200, bench.folder(q.get("dir", ""))) or True
            if path == "/api/saved":
                return self._json(200, bench.saved_buffer(q.get("path", ""))) or True
            if path == "/raw":           # a repo file with its own content type, for iframes
                p = bench.confine(q.get("path", ""))
                if not p.is_file():
                    return self._json(404, {"error": "not found"}) or True
                ctype = {".html": "text/html", ".csv": "text/csv", ".json": "application/json", ".md": "text/markdown"}.get(p.suffix, "text/plain")
                body = p.read_bytes()
                self.send_response(200); self.send_header("Content-Type", ctype + "; charset=utf-8"); self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return True
        except (ValueError, FileNotFoundError, KeyError) as e:
            return self._json(400 if isinstance(e, ValueError) else 404, {"error": str(e)}) or True
        except Exception as e:
            return self._json(500, {"error": f"{type(e).__name__}: {e}"}) or True
        return False

    def _bench_post(self, body):
        try:
            if self.path == "/api/open":
                return self._json(200, bench.open_program(path=body.get("path"), sas=body.get("sas")))
            if self.path == "/api/run_block":
                return self._json(200, bench.run_block(body["stem"], body["block"], body.get("engine", "rust"), body.get("session")))
            if self.path == "/api/term":
                return self._json(200, bench.term(body.get("cmd", ""), body.get("args", ""), body.get("stem"), body.get("block")))
            if self.path == "/api/session":
                return self._json(200, bench.attach(body.get("url", ""), body.get("name")))
            if self.path == "/api/session/detach":
                return self._json(200, bench.detach(body.get("id", "")))
            if self.path == "/api/exec":
                return self._json(200, bench.exec_code(body.get("code", ""), body.get("session")))
            if self.path == "/api/save":      # exp_42 2026-09-08: save a buffer copy under out/bench/buffers
                return self._json(200, bench.save_buffer(body.get("path", ""), body.get("text")))
            if self.path == "/api/listing":   # exp_42 2026-09-08: paste a SAS listing (text) or name a file under the repo (path)
                return self._json(200, bench.set_listing(body.get("stem", ""), text=body.get("text"), path=body.get("path")))
        except (ValueError, FileNotFoundError, KeyError) as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})
        return None

    def do_GET(self):
        path, _, qs = self.path.partition("?")
        if self._bench_get(path, qs):
            return
        if self.path in ("/", "/index.html"):
            body = (ROOT / "server/index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.split("?")[0] in ("/studio", "/studio.html", "/datamatch.js"):
            name = "studio.html" if self.path.startswith("/studio") else "datamatch.js"
            body = (ROOT / "server" / name).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ("text/html" if name.endswith(".html") else "application/javascript") + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/health":
            self._json(200, {"ok": True, "rust": RUST.exists(), "swipl": shutil.which("swipl") is not None})
        elif self.path == "/api/example":
            self._json(200, {"sas": (ROOT / "raw/test_vishnu.sas").read_text()})
        elif self.path == "/api/example_testdata":
            self._json(200, {"sas": (ROOT / "testdata/test_vishnu_testdata.sas").read_text()})
        elif self.path == "/api/example_fixed":
            self._json(200, {"sas": (ROOT / "testdata/test_vishnu_testdata_fixed.sas").read_text()})
        elif self.path == "/api/spec":
            self._json(200, json.loads((ROOT / "out/spec/sas.json").read_text()))
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path in ("/api/open", "/api/run_block", "/api/term", "/api/session", "/api/session/detach", "/api/exec", "/api/listing", "/api/save"):
            n = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._json(400, {"error": "body must be JSON"})
            self._bench_post(body); return
        if self.path == "/api/studio":
            n = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
                out = studio(body.get("sas", ""), run=bool(body.get("run")), blocks=bool(body.get("blocks")), prolog_pyspark=bool(body.get("prolog_pyspark")))
                self._json(200, out)
            except Exception as e:
                self._json(500, {"ok": False, "errors": [repr(e)]})
            return
        if self.path != "/api/convert":
            return self._json(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "body must be JSON"})
        sas = req.get("sas", "")
        if not sas.strip():
            return self._json(400, {"error": "field 'sas' is empty"})
        try:
            self._json(200, convert(sas, run=bool(req.get("run"))))
        except Exception as e:  # report, never hang the page
            self._json(500, {"ok": False, "errors": [f"{type(e).__name__}: {e}"]})

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8042)
    a = ap.parse_args()
    (ROOT / "out/api").mkdir(parents=True, exist_ok=True)
    print(f"exp_42 converter: http://localhost:{a.port}/   (POST /api/convert)   bench: http://localhost:{a.port}/bench")
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
