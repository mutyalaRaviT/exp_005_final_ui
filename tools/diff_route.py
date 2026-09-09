#!/usr/bin/env python3
"""tools/diff_route.py — the differential oracle for phase 2's route landings.

Why this exists: phase 2 replaces two Python backends (`raw/lineage_server/server/app.py`
on :8000, `raw/bench_stack/server/convert_api.py` on :8042) with one Rust API on :8110. A
route is only allowed to "land" — move from `oracle::forward` to reading the DuckDB store —
once its answers are proved identical to the Python implementation it replaces, file by
file. This is that proof tool.

**The old server is a regex scanner; the new one is a real parser.** They are allowed to
disagree, and when they do the parser is usually the one that is right. So a raw diff is
not the verdict — every difference must resolve to exactly one of two outcomes:
  - a Rust bug -> the route does not land
  - an accepted divergence -> a row in `docs/plan/bronze/bronze_phase2_route_ledger.md`'s
    "Accepted divergences" table, naming the file, the json_path, and why the parser is
    right, so it is never silently re-accepted and never silently reintroduced.
There is no third option. This tool has no `--force`, `--ignore`, or `--accept-all` flag,
on purpose: the only way to make a difference stop failing the run is to write down why in
the ledger. A tool that let a human wave a difference through without writing that sentence
would be worse than no tool — it would turn an unknown into a false reassurance.

**Usage**
    python3 tools/diff_route.py <question> [--corpus ankitha|exp42] [--json]

`<question>` is one of the twelve names in `ALL_ROUTES`
(`backend/api/src/lib.rs`): files, search, neighborhood, convert, blocklinks, edges,
source, file, blocks, tablegraph, story, run. Each is wired to exactly one corpus (below);
`--corpus` only needs to be given when you want the tool to check that it agrees with you,
or overridden — it is otherwise inferred from the question.

Exit codes: 0 only when every checked file diffs clean once accepted divergences are
subtracted (or the question has no oracle to check — see NO_ORACLE below); 1 when an
unexplained difference exists; 2 for a usage error or an oracle/the Rust API being down
(never a bare traceback — see `_fail()`).

**Corpora** (`docs/plan/plan/bronze/bronze_phase2_route_ledger.md`, Task 4 brief):
  - `ankitha`: the 25 files under `raw/lineage_server/inputs/ankitha_1/`, fileid
    `ankitha_1/<name>.sas` — checked against oracle_a, `:8000` (`app.py`, UI1's backend).
  - `exp42`: the SAS files under `raw/bench_stack/corpus/` and `raw/bench_stack/testdata/`,
    fileid = bare filename (no folder — `rust_inferred_duckdb::convert` takes the fileid
    from the path relative to whichever folder it is pointed at, and both exp42 folders are
    converted as their own root) — checked against oracle_b, `:8042` (`convert_api.py`, the
    Bench).

**On `unordered`.** `diff_json`'s `unordered` set names *dict keys*, not paths: a list found
under a key in that set is compared as a multiset (order-blind), everything else is
compared by index. This must never be "sort everything" — an order that carries meaning
(e.g. `story.makers`, which the Task 10 brief explicitly requires to come back in run order)
would have a real bug hidden by a blanket unordered flag. So the CLI below sets `unordered`
per question, per field, and the module docstring on `ROUTES` says why for each one. The one
genuine, well-evidenced case is the edge/link lists that both oracles and the Rust store
draw from the same underlying facts but iterate in a different order — the DuckDB fetch
order at :8000 versus Rust's own fold order (the design point named explicitly in the Task 4
brief). That reasoning applies identically to `/api/edges`'s `rows`, `neighborhood`'s
`edges`, `blocklinks`'s `links`, and `tablegraph`'s `edges` — four surfaces reading the same
kind of fact table. It does not apply to `nodes`, `seeds`, `story`, `files`, `hits`,
`tables`, or `makers` — none of those has the same "two engines walk the same table in a
different order" story, and `story.makers` is explicitly ordered by spec, so all of those
stay strictly ordered here; if a later task finds a genuine non-difference among those, it
extends this table with its own one-line reason, not a global switch.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = REPO_ROOT / "docs" / "plan" / "bronze" / "bronze_phase2_route_ledger.md"

RUST_BASE = "http://127.0.0.1:8110"
ORACLE_ANKITHA = "http://127.0.0.1:8000"   # raw/lineage_server/server/app.py (UI1's backend)
ORACLE_EXP42 = "http://127.0.0.1:8042"     # raw/bench_stack/server/convert_api.py (the Bench)

START_CMD = {
    RUST_BASE: (
        "cd backend/api && cargo run --release -- --db /tmp/lineageq_p2.duckdb "
        "(binds 127.0.0.1:8110 by default)"
    ),
    ORACLE_ANKITHA: (
        "cd raw/lineage_server/server && "
        "SAS_ROOTS=../inputs SAS_DB=../output/explorer.duckdb PYTHONPATH=../exp_2:. "
        "../.venv/bin/python app.py"
    ),
    ORACLE_EXP42: "cd raw/bench_stack && .venv/bin/python server/convert_api.py",
}


# --------------------------------------------------------------------------- diff engine
def diff_json(a: Any, b: Any, unordered: frozenset[str] | set[str] = frozenset(), _path: str = "") -> list[tuple]:
    """Walk `a` and `b` together and return every leaf where they disagree, as
    `(json_path, left, right)`. `unordered` names dict keys whose list value is compared as
    a multiset instead of by index (see the module docstring for which keys and why).

    `json_path` follows the same dotted/bracket notation as the brief's own tests
    (`"nodes[0].role"`), and, for a bare top-level list, starts directly with `"[i]"`.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        diffs: list[tuple] = []
        for key in sorted(set(a) | set(b)):
            sub_path = f"{_path}.{key}" if _path else key
            if key not in a:
                diffs.append((sub_path, None, b[key]))
            elif key not in b:
                diffs.append((sub_path, a[key], None))
            else:
                diffs.extend(_diff_value(a[key], b[key], unordered, sub_path, key))
        return diffs
    return _diff_value(a, b, unordered, _path, None)


def _diff_value(av: Any, bv: Any, unordered, path: str, field_name: str | None) -> list[tuple]:
    if isinstance(av, list) and isinstance(bv, list):
        if field_name is not None and field_name in unordered:
            return _diff_unordered_list(av, bv, path)
        diffs: list[tuple] = []
        if len(av) != len(bv):
            diffs.append((f"{path}.length" if path else "length", len(av), len(bv)))
        for i in range(min(len(av), len(bv))):
            diffs.extend(diff_json(av[i], bv[i], unordered, f"{path}[{i}]"))
        return diffs
    if isinstance(av, dict) and isinstance(bv, dict):
        return diff_json(av, bv, unordered, path)
    if av != bv:
        return [(path, av, bv)]
    return []


def _canon(x: Any) -> str:
    return json.dumps(x, sort_keys=True, default=str)


def _diff_unordered_list(av: list, bv: list, path: str) -> list[tuple]:
    """Multiset comparison: a genuinely reordered list yields no diffs; a list whose
    membership actually differs reports exactly what is missing (in `av`, not `bv`) and
    what is extra (in `bv`, not `av`), as canonical JSON, rather than pairing elements up
    positionally (which would misattribute a membership difference to whichever elements
    happened to sort adjacent)."""
    ca = Counter(_canon(x) for x in av)
    cb = Counter(_canon(x) for x in bv)
    diffs: list[tuple] = []
    for item in sorted((ca - cb).elements()):
        diffs.append((f"{path}[missing]", item, None))
    for item in sorted((cb - ca).elements()):
        diffs.append((f"{path}[extra]", None, item))
    return diffs


# --------------------------------------------------------------------------- the ledger
_TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")


def _table_rows(text: str, after_heading: str) -> list[list[str]]:
    """Every `| a | b | ... |` row of the first markdown table found after a line equal to
    `after_heading`, skipping the header row and the `|---|---|` separator row."""
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == after_heading)
    except StopIteration:
        return []
    rows = []
    seen_header = False
    for ln in lines[start + 1:]:
        m = _TABLE_ROW.match(ln.strip())
        if not m:
            if seen_header:
                break  # table ended
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if not seen_header:
            seen_header = True
            continue  # this is the header row
        if all(re.fullmatch(r"-+", c) for c in cells):
            continue  # the |---|---| separator
        rows.append(cells)
    return rows


def load_accepted(path: str | Path) -> set[tuple[str, str, str]]:
    """Parse the ledger's `## Accepted divergences` table into `(question, fileid,
    json_path)` triples. The fourth column ("why the parser is right") is documentation for
    humans, not consumed here — `filter_accepted` only ever checks the key."""
    text = Path(path).read_text()
    accepted = set()
    for cells in _table_rows(text, "## Accepted divergences"):
        if len(cells) < 3:
            continue
        question, fileid, json_path = cells[0], cells[1], cells[2]
        accepted.add((question, fileid, json_path))
    return accepted


def filter_accepted(diffs: list[tuple], accepted: set[tuple[str, str, str]], question: str, fileid: str) -> list[tuple]:
    """Drop exactly the diffs whose `(question, fileid, json_path)` is a row in the ledger.
    An accepted divergence is scoped to one question and one file — the same json_path
    accepted for one file must still fail for every other file that was never looked at."""
    return [d for d in diffs if (question, fileid, d[0]) not in accepted]


# --------------------------------------------------------------------------- HTTP, no deps
class OracleDown(Exception):
    """The server at `base` could not even be reached (connection refused, timeout, DNS,
    etc.) — the caller should be told the start command."""
    def __init__(self, base: str, detail: str):
        self.base = base
        self.detail = detail
        super().__init__(f"{base} unreachable: {detail}")


class OracleError(Exception):
    """The server at `base` is up and answered, but not usefully (a non-2xx status, or a
    2xx body that is not JSON) — the caller should NOT be told to start it; it is already
    running. The likeliest cause on the Rust side, before a route has landed, is a 404 for
    a question nothing has wired into `app()` yet."""
    def __init__(self, base: str, url: str, detail: str):
        self.base = base
        self.url = url
        self.detail = detail
        super().__init__(f"{url} -> {detail}")


def _http(method: str, url: str, body: dict | None = None, timeout: float = 30.0) -> Any:
    base = url.split("/api/")[0]
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                  headers={"Accept": "application/json",
                                           **({"Content-Type": "application/json"} if data else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        raise OracleError(base, url, f"HTTP {e.code}" + (f": {raw[:200]}" if raw.strip() else " (empty body)"))
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        raise OracleDown(base, str(e))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise OracleError(base, url, f"non-JSON response: {raw[:200]}")


def get(url: str) -> Any:
    return _http("GET", url)


def post(url: str, body: dict) -> Any:
    return _http("POST", url, body)


# --------------------------------------------------------------------------- corpora
def ankitha_files() -> list[str]:
    root = REPO_ROOT / "raw" / "lineage_server" / "inputs" / "ankitha_1"
    return [f"ankitha_1/{p.name}" for p in sorted(root.glob("*.sas"))]


def exp42_files() -> list[tuple[str, str]]:
    """Returns `(fileid, path-relative-to-bench-root)` pairs — fileid is the bare filename
    (see the module docstring on the exp42 corpus); the relative path is what the Bench's
    `/api/open` and `/api/file` need in their `path` field, since it serves two folders
    (`corpus/`, `testdata/`) under one root."""
    bench_root = REPO_ROOT / "raw" / "bench_stack"
    out = []
    for sub in ("corpus", "testdata"):
        d = bench_root / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.sas")):
            out.append((p.name, f"{sub}/{p.name}"))
    return out


# --------------------------------------------------------------------------- exp42 adapters
def _bench_open(rel_path: str) -> dict:
    return post(f"{ORACLE_EXP42}/api/open", {"path": rel_path})


def _shape_bench_open_as_file(open_resp: dict) -> dict:
    """Project the Bench's `/api/open` (whole program: source, every block's SAS+PySpark
    text, lineage facts) down to the `file()` wire shape the plan specifies: `{stem, path,
    ok, errors, blocks:[{id,n,kind,name,lines,warn,reads,writes}], receipts}` — deliberately
    **no `sas`, no `py`** per Task 9's brief, since dropping them is the entire point of
    splitting `file()` from `blocks()` (windowing, phase 3's pass mark)."""
    return {
        "stem": open_resp.get("stem"),
        "path": open_resp.get("path"),
        "ok": open_resp.get("ok"),
        "errors": open_resp.get("errors"),
        "blocks": [
            {k: b.get(k) for k in ("id", "n", "kind", "name", "lines", "warn", "reads", "writes")}
            for b in open_resp.get("blocks", [])
        ],
        "receipts": open_resp.get("receipts"),
    }


def _shape_bench_open_as_blocks(open_resp: dict) -> list:
    """Project onto `blocks()`'s wire shape. **Deliberately excludes `py_pretty`**: the
    Bench's per-block dict has no field that corresponds to it (`py_pretty` is Rust's own
    pretty-printed rendering, introduced in this phase — there is nothing in the old oracle
    to disagree with). Excluding a field because the old server structurally cannot produce
    it is not an accepted divergence — there is no comparison to accept or reject, only
    nothing to compare. It is documented here, in code, rather than as one ledger row per
    file, because it is not a per-file finding; it is a permanent shape fact. Once Task 9
    lands `blocks()` and knows Rust's real `py_pretty` semantics, it may still want its own
    check that `py_pretty` round-trips against `py` (a same-oracle consistency check, not an
    oracle diff) — that is Task 9's to add, not this tool's to fake here."""
    return [
        {k: b.get(k) for k in ("id", "n", "kind", "name", "lines", "sas", "py", "warn", "reads", "writes", "terms")}
        for b in open_resp.get("blocks", [])
    ]


def _shape_bench_lineage_as_tablegraph(open_resp: dict) -> dict:
    """Project the Bench's parsed lineage facts (`open_resp["lineage"]`: `ds_lineage` pairs
    `[dst, src]`, `ctl_lineage` triples `[dst, src, cond]`) onto `tablegraph()`'s
    `{tables, edges}` shape.

    `block_id` is reconstructed by matching an edge's destination table against whichever
    block's `writes` names that table (the same correlation Task 1's `edges.block_id`
    column makes durable on the Rust side) — this is the one non-trivial derivation here,
    and it is exactly what Task 10's own test (`e["block_id"] == "b_007"`) checks.

    **`tables[].kind` is deliberately left out of the comparison** (both sides still carry
    `name`): the Bench's lineage facts carry no per-table "kind" classification anywhere —
    `parse_facts`'s `schema` fact only names columns, not a kind — so there is no oracle
    value to check Rust's `kind` against, the same "nothing to compare" situation as
    `blocks().py_pretty` above. `block_id` on the *tables* list (as opposed to the edges
    list, where it is derived above) is left out for the same reason. Task 10 should revisit
    this the day it knows what `kind` actually means for a table."""
    lineage = open_resp.get("lineage", {}) or {}
    blocks = open_resp.get("blocks", [])
    writer_of = {b.get("writes"): b.get("id") for b in blocks if b.get("writes")}

    edges = []
    for dst, src in lineage.get("ds_lineage", []):
        edges.append({"src": src, "dst": dst, "kind": "ds", "block_id": writer_of.get(dst)})
    for triple in lineage.get("ctl_lineage", []):
        dst, src = triple[0], triple[1]
        edges.append({"src": src, "dst": dst, "kind": "ctl", "block_id": writer_of.get(dst)})

    names = sorted({e["src"] for e in edges} | {e["dst"] for e in edges})
    tables = [{"name": n} for n in names]
    return {"tables": tables, "edges": edges}


def _project(d: dict, keys: list[str]) -> dict:
    return {k: d.get(k) for k in keys}


# --------------------------------------------------------------------------- the route table
class Route:
    """One question's check plan: which corpus it is tied to, how to iterate that corpus
    (one call for the whole corpus, or one call per file), how to fetch and shape both
    sides, and which fields are order-blind. `no_oracle`, when set, means this question has
    nothing to diff against — the CLI reports that and exits 0 rather than inventing a
    comparison."""

    def __init__(self, corpus: str, unordered: set[str], no_oracle: str | None = None):
        self.corpus = corpus
        self.unordered = unordered
        self.no_oracle = no_oracle


ROUTES: dict[str, Route] = {
    "files": Route("ankitha", unordered=set()),
    "search": Route("ankitha", unordered=set()),
    "neighborhood": Route("ankitha", unordered={"edges"}),
    "blocklinks": Route("ankitha", unordered={"links"}),
    "edges": Route("ankitha", unordered={"rows"}),
    "convert": Route("ankitha", unordered=set(),
                      no_oracle="new surface (Task 6b brief): the report shape "
                                "({files,ok,failed,blocks,node4,edges,fold_ms,store_ms,total_ms}) "
                                "has no equivalent in either Python oracle — it is not a "
                                "replacement for an existing answer, it is new. Land via its "
                                "own pass mark (idempotent-convert test), not this tool."),
    "source": Route("exp42", unordered=set(),
                     no_oracle="no brief states source()'s wire shape or a diff_route "
                               "invocation for it (Task 8 creates routes/source.rs but its "
                               "brief never specifies the JSON it returns). Guessing a shape "
                               "here would either assert a false contract or hide a real "
                               "mismatch under a wrong comparison. Task 8 must extend this "
                               "table with the real shape (and, if a Bench-side raw-text "
                               "read is the intended oracle, `GET /api/file?path=` "
                               "-> {path,text,size} is the obvious candidate) when it lands "
                               "the route."),
    "file": Route("exp42", unordered=set()),
    "blocks": Route("exp42", unordered=set()),
    "tablegraph": Route("exp42", unordered={"edges"}),
    "story": Route("exp42", unordered=set(),
                    no_oracle="story() takes a table name, not a fileid, but this tool "
                              "iterates the exp42 corpus by file — there is no brief-given "
                              "rule for which table's story to check for a given file "
                              "(the one worked example, sales.final_summary for "
                              "test_vishnu_testdata_fixed.sas, is a single fixture, not a "
                              "corpus-wide rule). Task 10 should either add a --table flag "
                              "or a small fixture map (fileid -> table) before landing "
                              "story() through this tool, rather than have it guess a table "
                              "per file."),
    "run": Route("ankitha", unordered=set(),
                 no_oracle="new surface (Task 12 brief): a dual-engine run (Rust/Prolog "
                           "interpreter vs Spark) with no shape-compatible equivalent in "
                           "either oracle. Task 12's own brief lands it via a direct pass-"
                           "mark curl loop against known-good verdicts, not an oracle diff."),
}


# --------------------------------------------------------------------------- per-question fetch
def _rust_get(path_and_query: str) -> Any:
    return get(f"{RUST_BASE}{path_and_query}")


def _one_check(question: str, fileid: str, rust_json: Any, oracle_json: Any, unordered: set[str]) -> list[tuple]:
    return diff_json(oracle_json, rust_json, unordered=unordered)


def run_question(question: str, corpus: str | None, verbose: bool) -> tuple[bool, list[dict]]:
    """Returns `(clean, report_rows)`. Raises `OracleDown` (caught by `main`) if either the
    Rust API or the relevant oracle cannot be reached — never partway through a silent
    partial run; every file this question would have checked is left unchecked rather than
    reported clean."""
    route = ROUTES.get(question)
    if route is None:
        print(f"[diff_route] unknown question {question!r} — one of: {', '.join(sorted(ROUTES))}", file=sys.stderr)
        raise SystemExit(2)
    if corpus is not None and corpus != route.corpus:
        print(
            f"[diff_route] {question!r} is checked against the {route.corpus!r} corpus, not "
            f"{corpus!r} ({question!r}'s oracle only serves that corpus) — omit --corpus or "
            f"pass --corpus {route.corpus}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    corpus = route.corpus

    if route.no_oracle:
        if verbose:
            print(f"[diff_route] {question}: no oracle to check — {route.no_oracle}")
        return True, [{"fileid": None, "diffs": [], "note": route.no_oracle}]

    accepted = load_accepted(LEDGER_PATH)
    rows: list[dict] = []
    clean = True

    if question == "files":
        oracle_json = get(f"{ORACLE_ANKITHA}/api/files")
        rust_json = _rust_get("/api/files")
        d = filter_accepted(_one_check(question, "*", rust_json, oracle_json, route.unordered), accepted, question, "*")
        rows.append({"fileid": "*", "diffs": d})
        clean = not d

    elif question == "search":
        oracle_json = get(f"{ORACLE_ANKITHA}/api/search?q=")
        rust_json = _rust_get("/api/search?q=")
        d = filter_accepted(_one_check(question, "*", rust_json, oracle_json, route.unordered), accepted, question, "*")
        rows.append({"fileid": "*", "diffs": d})
        clean = not d

    elif question == "neighborhood":
        for fileid in ankitha_files():
            qs = f"file={urllib.parse.quote(fileid, safe='')}&up=1&down=1"
            oracle_json = get(f"{ORACLE_ANKITHA}/api/neighborhood?{qs}")
            rust_json = _rust_get(f"/api/neighborhood?{qs}")
            d = filter_accepted(_one_check(question, fileid, rust_json, oracle_json, route.unordered), accepted, question, fileid)
            rows.append({"fileid": fileid, "diffs": d})
            clean = clean and not d

    elif question == "blocklinks":
        files_csv = urllib.parse.quote(",".join(ankitha_files()), safe=",")
        oracle_json = get(f"{ORACLE_ANKITHA}/api/blocklinks?files={files_csv}")
        rust_json = _rust_get(f"/api/blocklinks?files={files_csv}")
        d = filter_accepted(_one_check(question, "*", rust_json, oracle_json, route.unordered), accepted, question, "*")
        rows.append({"fileid": "*", "diffs": d})
        clean = not d

    elif question == "edges":
        files_csv = urllib.parse.quote(",".join(ankitha_files()), safe=",")
        oracle_json = get(f"{ORACLE_ANKITHA}/api/edges?files={files_csv}&limit=10000")
        rust_json = _rust_get(f"/api/edges?files={files_csv}&limit=10000")
        d = filter_accepted(_one_check(question, "*", rust_json, oracle_json, route.unordered), accepted, question, "*")
        rows.append({"fileid": "*", "diffs": d})
        clean = not d

    elif question == "file":
        for fileid, rel_path in exp42_files():
            open_resp = _bench_open(rel_path)
            oracle_json = _shape_bench_open_as_file(open_resp)
            rust_json = _rust_get(f"/api/file?fileid={urllib.parse.quote(fileid)}")
            d = filter_accepted(_one_check(question, fileid, rust_json, oracle_json, route.unordered), accepted, question, fileid)
            rows.append({"fileid": fileid, "diffs": d})
            clean = clean and not d

    elif question == "blocks":
        for fileid, rel_path in exp42_files():
            open_resp = _bench_open(rel_path)
            oracle_json = _shape_bench_open_as_blocks(open_resp)
            rust_json = _rust_get(f"/api/blocks?fileid={urllib.parse.quote(fileid)}&from=0&to=999999")
            d = filter_accepted(_one_check(question, fileid, rust_json, oracle_json, route.unordered), accepted, question, fileid)
            rows.append({"fileid": fileid, "diffs": d})
            clean = clean and not d

    elif question == "tablegraph":
        for fileid, rel_path in exp42_files():
            open_resp = _bench_open(rel_path)
            oracle_json = _shape_bench_open_as_tablegraph(open_resp)
            rust_json = _rust_get(f"/api/tablegraph?fileid={urllib.parse.quote(fileid)}")
            # tables[].kind has no oracle equivalent (see the adapter's doc comment) — project
            # both sides down to {name} before diffing so that gap is not reported as a diff.
            if isinstance(rust_json, dict) and isinstance(rust_json.get("tables"), list):
                rust_json = dict(rust_json)
                rust_json["tables"] = [_project(t, ["name"]) for t in rust_json["tables"]]
            d = filter_accepted(_one_check(question, fileid, rust_json, oracle_json, route.unordered), accepted, question, fileid)
            rows.append({"fileid": fileid, "diffs": d})
            clean = clean and not d

    else:
        print(f"[diff_route] question {question!r} is registered but run_question has no case for it (bug)", file=sys.stderr)
        raise SystemExit(2)

    return clean, rows


def _shape_bench_open_as_tablegraph(open_resp: dict) -> dict:
    return _shape_bench_lineage_as_tablegraph(open_resp)


# --------------------------------------------------------------------------- CLI
def _print_report(question: str, clean: bool, rows: list[dict]) -> None:
    total_diffs = sum(len(r["diffs"]) for r in rows)
    for r in rows:
        if r["diffs"]:
            print(f"[diff_route] {question} {r['fileid']}: {len(r['diffs'])} unexplained difference(s)")
            for path, left, right in r["diffs"]:
                print(f"    {path}: oracle={left!r}  rust={right!r}")
        elif r.get("note"):
            pass  # already printed by run_question in verbose mode
    checked = sum(1 for r in rows if r["fileid"] is not None)
    if clean:
        print(f"[diff_route] {question}: clean — {checked} file(s)/call(s) checked, {total_diffs} diffs, all accepted or none found")
    else:
        print(f"[diff_route] {question}: NOT clean — {checked} file(s)/call(s) checked, {total_diffs} unexplained diff(s)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Differential oracle: does the Rust API's answer for "
                                              "<question> match the Python implementation it replaces?")
    ap.add_argument("question", choices=sorted(ROUTES))
    ap.add_argument("--corpus", choices=["ankitha", "exp42"], default=None)
    ap.add_argument("--json", action="store_true", help="emit a machine-readable report instead of text")
    args = ap.parse_args(argv)

    try:
        clean, rows = run_question(args.question, args.corpus, verbose=not args.json)
    except OracleDown as e:
        target = "the Rust API" if e.base == RUST_BASE else "an oracle"
        cmd = START_CMD.get(e.base, "(no known start command for this base URL)")
        msg = f"{target} at {e.base} is not reachable: {e.detail}\nstart it with:\n  {cmd}"
        if args.json:
            print(json.dumps({"ok": False, "error": msg}))
        else:
            print(f"[diff_route] {msg}", file=sys.stderr)
        return 2
    except OracleError as e:
        target = "the Rust API" if e.base == RUST_BASE else "an oracle"
        extra = ""
        if e.base == RUST_BASE and "404" in e.detail:
            extra = (f"\n{args.question!r} is not landed yet (or not wired into app()) — "
                     f"see backend/api/src/routes/mod.rs and lib.rs::ALL_ROUTES/LANDED.")
        msg = f"{target} at {e.url} answered but not usefully: {e.detail}{extra}"
        if args.json:
            print(json.dumps({"ok": False, "error": msg}))
        else:
            print(f"[diff_route] {msg}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "question": args.question,
            "ok": clean,
            "rows": [
                {"fileid": r["fileid"], "diffs": r["diffs"], **({"note": r["note"]} if r.get("note") else {})}
                for r in rows
            ],
        }, default=str))
    else:
        _print_report(args.question, clean, rows)

    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
