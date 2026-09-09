"""Answers the explorer's questions: neighborhood, story, Excel, edits.

Everything here is deterministic Python — no AI, sorted iteration, same
input -> same output. All user-facing strings use data-flow notation
(``x -> y`` reads as "data moves from x into y"), never "depends on".

The three edge levels stay separate and each carries its provenance:

    block   BLOCK_FLOW    fact        the source literally says it
    file    FILE_FLOW     inferred    resolver deduction inside one file
    project writer -> reader across files, also inferred
    (human edits are a fourth, separate class: human_gold)

Parse-on-demand: a file is analyzed the first time a question needs it and
ingested into the DuckDB store. A fileid is the file's STABLE relative path
(``<folder>/<name>``), so a fileid outlives the bytes it points at: the
in-memory parse cache is therefore keyed on the file's content hash and
re-parses the moment the file on disk changes.
"""
import io
import json
import re
import threading
from dataclasses import asdict
from datetime import datetime
from functools import wraps
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.compute as pc
from openpyxl import Workbook

from sas_lineage.exporter import COLUMNS, make_fileid, schema_of
from sas_lineage.registry import file_hash
from sas_lineage.ui_export import (build_file_entry, project_edges,
                                    project_edges_blocks)

from indexer import common_base
from orderer import Flow, compute_order
from scanners import active_scanner, scan_term

#: the only edits a customer can record against a flow, sorted:
#:   add      a flow the engine never found
#:   confirm  the engine row is right (and, after a re-parse, still right)
#:   correct  the engine row was wrong — here is the right flow
#:   reject   the engine row is wrong and there is nothing to put in its place
ACTIONS = ("add", "confirm", "correct", "reject")

PROVENANCE_BY_EDGE_TYPE = {
    "BLOCK_FLOW": "fact",
    "FILE_FLOW": "inferred",
    "PROJECT_FLOW": "inferred",
}

#: sheet `provided` = the fixed export contract + how the row was obtained
PROVIDED_COLUMNS = COLUMNS + ["edge_type", "provenance"]

#: sheet `customer_changes` = every HUMAN_GOLD row
CHANGE_COLUMNS = ["edited_at", "editor", "action", "src", "dst",
                  "table_name", "level", "comment"]

#: sheet `final_edges` = the merged view (engine rows with un-flagged
#: customer edits applied) that `/api/edges` also serves, page by page
FINAL_EDGE_COLUMNS = ["src", "dst", "table_name", "level", "provenance", "link"]

#: Excel caps a sheet at 1,048,576 rows (including the header); the last
#: data row is reserved for an overflow notice once the merge is bigger
MAX_XLSX_ROWS = 1_048_575

#: the web app's deep-link route the Excel HYPERLINK column opens
VIEW_URL_BASE = "http://localhost:5173/view"

#: default/streaming page size for Service.final_edges / GET /api/edges
DEFAULT_EDGES_LIMIT = 200

#: the three views of one grid (see the spec, section 7):
#:   engine  the tool's latest parse — read-only, only the engine replaces it
#:   human   the customer's own rows — the only place a person edits, and
#:           where the `requires_check` review queue lives
#:   final   the two merged (`final_edges`) — read-only
ARROW_VIEWS = ("engine", "human", "final")

#: one column contract for all three views, so the browser's grid can swap
#: views without changing a single accessor. `fileid` comes FIRST because it
#: is what the grid opens the row's SAS code by: a block id is only unique
#: WITHIN a file, so the row itself has to carry the file it belongs to.
#: `freshness` (green | yellow | red) is LAST so existing index-based
#: readers of the earlier columns stay valid
EDGE_ARROW_COLUMNS = ["fileid", "src", "dst", "table_name", "level",
                      "provenance", "block_id", "requires_check",
                      "freshness"]

#: hard ceiling on one neighborhood, so a very common table cannot drag the
#: whole 30k-file tree into a single answer
MAX_NEIGHBORHOOD = 200

#: a line that OPENS a SAS step — the anchor `block_line_starts` counts by
_STEP_HEAD_RE = re.compile(r"\s*(data|proc)\b", re.IGNORECASE)


def _detail_edge(row: dict, level: str, provenance: str) -> dict:
    """A block/file edge as the screen renders it: ``src -> dst``."""
    return {
        "src": row["src_name"], "dst": row["dst_name"],
        "src_ref": row["src_ref"], "dst_ref": row["dst_ref"],
        "block": row["block"], "level": level, "provenance": provenance,
    }


def _uncommented_lines(source: str) -> list[str]:
    """`source` split into lines with every `/* ... */` comment blanked out.

    Blanking (instead of deleting) keeps line numbers exact, which is the
    whole point here: a commented-out `data` step must not be mistaken for a
    real one, and the lines around it must not shift.
    """
    masked, depth, i = [], 0, 0
    while i < len(source):
        two = source[i:i + 2]
        if two == "/*":
            depth += 1
            masked.append("  ")
            i += 2
        elif two == "*/" and depth:
            depth -= 1
            masked.append("  ")
            i += 2
        else:
            char = source[i]
            masked.append(char if (char == "\n" or not depth) else " ")
            i += 1
    return "".join(masked).splitlines()


def block_line_starts(source: str, block_ids: list[str]) -> list[int]:
    """1-based line in `source` where each block in `block_ids` starts.

    The browser scrolls a file's code to a block by this number, so the
    answer is always an int >= 1 and this never raises — a wrong-but-close
    line is far better for a reader than an exception.

    Two rules, in order:

    1. The id appears LITERALLY in the source — an injected
       ``/*BLOCKID b_1_00993f29*/`` annotation. Then its line is the 1-based
       number of the FIRST line containing it. This is exact.
    2. Otherwise, positional: collect in order the 1-based numbers of the
       lines that START a SAS step (first word `data` or `proc`, matched
       case-insensitively on a word boundary, ignoring anything inside a
       ``/* */`` comment). The i-th block — by its index in `block_ids` —
       takes the i-th such header line. If that index has no candidate, the
       last candidate found is used, or 1 when the file has none.

    Rule 2 is BEST-EFFORT and deliberately so. Blocks that come from a macro
    instance (`<def_id>#<call_no>`) are placed at their CALL site by the
    analyzer, so there is no header line of their own to land on — they get
    the nearest header instead of nothing. Injected annotations (rule 1) are
    the accurate path, and the pipeline emits them for all incoming code.
    """
    raw_lines = source.splitlines()
    candidates = [n for n, line in enumerate(_uncommented_lines(source),
                                             start=1)
                  if _STEP_HEAD_RE.match(line)]
    starts = []
    for index, block_id in enumerate(block_ids):
        literal = next((n for n, line in enumerate(raw_lines, start=1)
                        if block_id and block_id in line), None)
        if literal is not None:
            starts.append(literal)
        elif index < len(candidates):
            starts.append(candidates[index])
        else:
            starts.append(candidates[-1] if candidates else 1)
    return starts


def order_payload(order: dict, labels: dict[str, str]) -> dict:
    """OrderResults as JSON dicts, keyed by fileid.

    Structural fields stay fileids so the screen can link a cycle member back
    to its node; the `reasoning` sentence — which a person reads — gets the
    fileids swapped for readable file names, and `label` carries that name.
    Longest fileid first, so no id is rewritten by a prefix of another.
    """
    swaps = sorted(labels.items(), key=lambda kv: (-len(kv[0]), kv[0]))
    payload = {}
    for fileid in sorted(order):
        row = asdict(order[fileid])
        for raw, label in swaps:
            row["reasoning"] = row["reasoning"].replace(raw, label)
        row["label"] = labels.get(fileid, fileid)
        payload[fileid] = row
    return payload


def _cell(value):
    """DuckDB value -> something openpyxl can write."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    return value


def _serialized(method):
    """Run this call while holding the service's lock.

    One `Service` owns ONE DuckDB connection, and the merge it queries lives
    in connection-global temp views (`_scope_fileids`, `_provided_edges`,
    `_merged_edges`). Requests arrive concurrently — the screen fires the
    grid's whole-view Arrow load while the graph and run order are still in
    flight — so two threads would otherwise ingest the same file twice (a
    primary-key collision) or read one scope's rows through another scope's
    views. Serializing the store-touching calls keeps both honest; the lock
    is reentrant, so these methods can call each other.
    """
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


def _as_reader(result) -> "pa.RecordBatchReader":
    """DuckDB's `.arrow()` -> a record batch reader, whichever it handed back
    (newer DuckDB streams a reader; older versions materialize a table)."""
    if isinstance(result, pa.Table):
        return pa.RecordBatchReader.from_batches(result.schema,
                                                  result.to_batches())
    return result


def serialize_arrow_stream(reader: "pa.RecordBatchReader") -> bytes:
    """Arrow IPC bytes for a record-batch reader, with every string column
    dictionary-encoded first.

    Edge columns repeat heavily (tens of thousands of distinct file/table
    names across millions of rows), so shipping each distinct string once
    plus int32 indices instead of every string in full cuts the wire size
    several-fold. Arrow JS reads dictionary vectors natively — iteration
    yields the decoded strings, so `toColumns` in the web app is unchanged.
    The table is combined to one chunk so each column carries exactly one
    dictionary (no delta/replacement dictionaries in the stream)."""
    table = reader.read_all().combine_chunks()
    columns = []
    for name in table.schema.names:
        col = table.column(name)
        if pa.types.is_string(col.type):
            encoded_col = pc.dictionary_encode(col)
            # adaptive: an all-distinct column (block ids) grows when
            # encoded — keep whichever representation is smaller
            if encoded_col.nbytes < col.nbytes:
                col = encoded_col
        columns.append(col)
    encoded = pa.table(columns, names=list(table.schema.names))
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, encoded.schema) as writer:
        writer.write_table(encoded)
    return sink.getvalue().to_pybytes()


def _hyperlink(fileid, block_id) -> str:
    """An Excel HYPERLINK formula that opens the web app centered on this
    edge's file (and block, when the edge has one) with +/-2 connected
    files — the same deep link `?file=&block=&depth=` the app parses on
    load."""
    return (f'=HYPERLINK("{VIEW_URL_BASE}?file={fileid}'
            f'&block={block_id or ""}&depth=2","open")')


class Service:
    """Neighborhood / story / Excel / edits over one store + one index."""

    def __init__(self, store, indexer, roots, history=None):
        self.store = store
        self.indexer = indexer
        #: the shadow git repo (history.EstateHistory) behind code saves and
        #: the code/edge timeline; None disables saving (read-only server)
        self.history = history
        self.roots = [Path(r) for r in roots]
        # the indexer's base, so both mint the same fileid for the same file
        self._base_dir = common_base(self.roots)
        self._paths: dict[str, Path] = {}    # fileid -> path on disk
        #: fileid -> (content hash at parse time, parsed file entry)
        self._entries: dict[str, tuple[str, dict]] = {}
        #: fileid -> content hash this session last ingested into the store
        self._ingested: dict[str, str] = {}
        #: one store, one connection, connection-global temp views: every
        #: store-touching call runs one at a time (see `_serialized`).
        #: The indexer holds that SAME connection and reads it from its own
        #: calls (typeahead, status), so its lock is adopted here rather than
        #: a second one created — two locks would not stop the two of them
        #: colliding on the one connection.
        self._lock = getattr(indexer, "lock", None) or threading.RLock()

    # ---- paths & parsing --------------------------------------------------

    def _remember(self, path: Path) -> str:
        path = Path(path)
        fileid = make_fileid(path, self._base_dir)
        self._paths[fileid] = path
        return fileid

    def _path_for(self, fileid: str) -> Path:
        """fileid -> the file on disk: cache, then the index's `mentions`
        table, then a name-scoped walk of the roots (the path must mint the
        same fileid back)."""
        cached = self._paths.get(fileid)
        if cached is not None and cached.is_file():
            return cached
        row = self.store.con.execute(
            "SELECT path FROM mentions WHERE fileid = ? ORDER BY path LIMIT 1",
            [fileid]).fetchone()
        if row and Path(row[0]).is_file():
            self._paths[fileid] = Path(row[0])
            return self._paths[fileid]
        name = fileid.rsplit("/", 1)[-1]
        for root in self.roots:
            for candidate in sorted(Path(root).rglob(name)):
                if make_fileid(candidate, self._base_dir) == fileid:
                    self._paths[fileid] = candidate
                    return candidate
        raise FileNotFoundError(f"no source file on disk for fileid {fileid}")

    def _entry(self, fileid: str) -> dict:
        """Parse-on-demand, cached by content hash: a fileid is a stable path,
        so the same id can point at new bytes tomorrow — the cache re-parses
        as soon as the file's hash moves."""
        path = self._path_for(fileid)
        digest = file_hash(path.read_text(errors="ignore"))
        cached = self._entries.get(fileid)
        if cached is None or cached[0] != digest:
            cached = (digest, build_file_entry(path, self._base_dir))
            self._entries[fileid] = cached
        return cached[1]

    def _entries_for(self, fileids) -> list[dict]:
        """Entries for the fileids that still exist on disk, sorted."""
        entries = []
        for fileid in sorted(set(fileids)):
            try:
                entries.append(self._entry(fileid))
            except FileNotFoundError:
                continue
        return entries

    @_serialized
    def _ensure_ingested(self, fileids) -> None:
        """Persist the parse of every fileid the store has not seen — or has
        stored from OTHER bytes.

        A fileid is a stable path, so "already stored" cannot mean "the id is
        in the store": it has to mean "stored from exactly these bytes". This
        session remembers the hash it ingested each fileid at; a fileid it has
        not ingested itself is re-ingested once (`ingest_file` replaces the
        file's rows, so the engine view only ever holds the latest parse)."""
        stored = {r[0] for r in self.store.con.execute(
            "SELECT DISTINCT fileid FROM blocks").fetchall()}
        for fileid in sorted(set(fileids)):
            try:
                path = self._path_for(fileid)
            except FileNotFoundError:
                continue
            digest = file_hash(path.read_text(errors="ignore"))
            if fileid in stored and self._ingested.get(fileid) == digest:
                continue
            self.store.ingest_file(path, self._base_dir)
            self._ingested[fileid] = digest
            # engine rows for this file are now the latest parse only
            # (ingest_file DELETE + INSERTs); flag any human edit whose
            # block id fell out of that latest parse
            self.indexer.flag_stale_edits(fileid)

    # ---- store-backed search (sources) -------------------------------------

    def roots_signature(self) -> str:
        """One string naming exactly which tree a sync covered."""
        return ",".join(sorted(str(Path(r).resolve()) for r in self.roots))

    @_serialized
    def sources_ready(self) -> bool:
        """The DuckDB scanner is authoritative only after a full sync of the
        CURRENT roots — never silently partial before that."""
        row = self.store.con.execute(
            "SELECT value FROM sync_meta WHERE key = 'synced_roots'"
        ).fetchone()
        return bool(row) and row[0] == self.roots_signature()

    @_serialized
    def scan_sources_term(self, term: str) -> list[str]:
        """`scan_term` semantics (case-insensitive literal substring) over
        the stored raw sources instead of the disk."""
        return [r[0] for r in self.store.con.execute(
            "SELECT fileid FROM sources WHERE contains(lower(source), ?) "
            "ORDER BY fileid", [term.strip().lower()]).fetchall()]

    @_serialized
    def sync_sources(self) -> dict:
        """Tree-wide hash-gated refresh: walk the roots, reconvert only files
        whose bytes moved (or that the store never fully ingested), drop rows
        for files gone from disk, and stamp the sync so the DuckDB scanner
        becomes authoritative (`sources_ready`)."""
        paths = sorted(
            {p for root in self.roots for p in Path(root).rglob("*.sas")})
        stored = dict(self.store.con.execute(
            "SELECT fileid, sashashcode FROM sources").fetchall())
        known = {r[0] for r in self.store.con.execute(
            "SELECT fileid FROM files").fetchall()}

        on_disk, ingested = set(), 0
        for path in paths:
            fileid = make_fileid(path, self._base_dir)
            on_disk.add(fileid)
            digest = file_hash(path.read_text(errors="ignore"))
            if stored.get(fileid) == digest:
                continue                    # bytes unchanged, fully stored
            self.store.ingest_file(path, self._base_dir)
            self._ingested[fileid] = digest
            self._paths[fileid] = path
            self.indexer.flag_stale_edits(fileid)
            ingested += 1

        removed = 0
        for fileid in sorted((set(stored) | known) - on_disk):
            self.store.remove_file(fileid)
            self.store.con.execute(
                "DELETE FROM mentions WHERE fileid = ?", [fileid])
            self._entries.pop(fileid, None)
            self._ingested.pop(fileid, None)
            self._paths.pop(fileid, None)
            removed += 1

        synced_at = datetime.now().isoformat(sep=" ", timespec="seconds")
        self.store.con.execute("DELETE FROM sync_meta")
        self.store.con.executemany(
            "INSERT INTO sync_meta VALUES (?, ?)",
            [("synced_at", synced_at),
             ("synced_roots", self.roots_signature()),
             ("files_on_disk", str(len(paths)))])
        return {"files_on_disk": len(paths), "ingested": ingested,
                "removed": removed, "synced_at": synced_at}

    @_serialized
    def sync_status(self) -> dict:
        """What /api/status shows about store-backed search coverage."""
        meta = dict(self.store.con.execute(
            "SELECT key, value FROM sync_meta").fetchall())
        return {
            "synced_at": meta.get("synced_at"),
            "files_on_disk": (int(meta["files_on_disk"])
                              if "files_on_disk" in meta else None),
            "sources_indexed": self.store.con.execute(
                "SELECT count(*) FROM sources").fetchone()[0],
        }

    # ---- seeds ------------------------------------------------------------

    def _seed_fileids(self, table=None, file=None) -> list[str]:
        if file:
            return self._resolve_file(file)
        if not table:
            raise ValueError("neighborhood needs a table= or a file=")
        fileids = self.indexer.files_mentioning(table)
        if not fileids:
            # unknown term: the synced store answers without touching the
            # disk (files there are already ingested); otherwise scan the
            # tree live, then remember what we found
            if active_scanner(self.sources_ready()) == "duckdb":
                fileids = self.scan_sources_term(table)
            else:
                fileids = []
                for path in sorted(scan_term(table, self.roots)):
                    fileids.append(self._remember(path))
                    self.store.ingest_file(path, self._base_dir)
        return sorted(set(fileids))

    def _resolve_file(self, file: str) -> list[str]:
        """Accept a fileid (`<folder>/<name>`) or a plain file name — a fileid
        always carries its folder, a bare name never does."""
        if "/" in file:
            return [file]
        name = file.rsplit("/", 1)[-1]
        rows = self.store.con.execute(
            "SELECT DISTINCT fileid FROM files WHERE sasfilename = ? "
            "ORDER BY fileid", [name]).fetchall()
        if rows:
            return [r[0] for r in rows]
        found = sorted({p for root in self.roots for p in Path(root).rglob(name)})
        return [self._remember(p) for p in found]

    # ---- neighborhood -----------------------------------------------------

    @_serialized
    def neighborhood(self, *, table=None, file=None, depth=1,
                     up=None, down=None) -> dict:
        """Nodes + project-level edges around a seed, with run-order scores
        and the story told in data-flow sentences.

        `up`/`down` bound the walk per direction (hops against the data flow
        vs hops with it); either defaults to `depth`, so `depth=2` alone
        still means "2 hops both ways". Every node carries its `role` —
        seed | up | down | both — and the payload names its `seeds`, so the
        screen can ring the focus and tint each side of the flow.
        """
        up = int(depth) if up is None else int(up)
        down = int(depth) if down is None else int(down)
        seeds = self._seed_fileids(table=table, file=file)
        upstream = self._directed_reach(seeds, up, "up")
        downstream = self._directed_reach(seeds, down, "down")
        included = set(seeds) | upstream | downstream
        roles = {}
        for fileid in included:
            if fileid in set(seeds):
                roles[fileid] = "seed"
            elif fileid in upstream and fileid in downstream:
                roles[fileid] = "both"
            else:
                roles[fileid] = "up" if fileid in upstream else "down"

        entries = self._entries_for(sorted(included)[:MAX_NEIGHBORHOOD])
        fileids = [e["fileid"] for e in entries]
        self._ensure_ingested(fileids)

        raw_edges = project_edges(entries)
        order = compute_order(
            [Flow(e["src_file"], e["dst_file"], tuple(e["tables"]))
             for e in raw_edges],
            nodes=fileids)
        labels = self._labels(entries)

        nodes = [{
            "id": e["fileid"], "label": labels[e["fileid"]],
            "folder": e["folder"], "score": order[e["fileid"]].score,
            "cyclic": order[e["fileid"]].cyclic,
            "role": roles.get(e["fileid"], "seed"),
        } for e in entries]
        edges = [{
            "src": e["src_file"], "dst": e["dst_file"],
            "tables": list(e["tables"]), "level": "project",
            "provenance": "inferred",
        } for e in raw_edges]
        present = {e["fileid"] for e in entries}
        return {
            "nodes": nodes,
            "edges": edges,
            "seeds": [s for s in sorted(set(seeds)) if s in present],
            "story": self._story(seeds, raw_edges, order, labels),
            "order": order_payload(order, labels),
        }

    def _directed_reach(self, seeds, hops: int, direction: str) -> set:
        """Files reached from `seeds` in at most `hops` directed hops
        (seeds excluded). Upstream follows what a file READS back to the
        files that WRITE those tables; downstream follows what it WRITES
        forward to the files that READ them. The mention index only nominates
        candidates — the candidate's own parse decides whether it actually
        sits on the asked-for side of the flow."""
        reached, frontier = set(), set(seeds)
        for _ in range(max(int(hops), 0)):
            nxt = set()
            for fileid in sorted(frontier):
                for term in self._tables_of(fileid, "reads" if direction ==
                                            "up" else "writes"):
                    for other in self.indexer.files_mentioning(term):
                        if other in reached or other in nxt or other in seeds:
                            continue
                        pool = self._tables_of(other, "writes" if direction ==
                                               "up" else "reads")
                        if term in pool:
                            nxt.add(other)
            if not nxt:
                break
            reached |= nxt
            frontier = nxt
            if len(reached) >= MAX_NEIGHBORHOOD:
                break
        return reached

    def _tables_of(self, fileid: str, side: str) -> set[str]:
        """The canonical tables a file reads or writes, lowercased to match
        the mention index's terms."""
        try:
            entry = self._entry(fileid)
        except FileNotFoundError:
            return set()
        return {t.lower() for t in entry[side]}

    @staticmethod
    def _labels(entries: list[dict]) -> dict[str, str]:
        """Readable node names: the file name, qualified by its folder only
        when two included files share a name."""
        counts: dict[str, int] = {}
        for e in entries:
            counts[e["name"]] = counts.get(e["name"], 0) + 1
        return {
            e["fileid"]: (e["name"] if counts[e["name"]] == 1
                          else f"{e['folder']}/{e['name']}")
            for e in entries
        }

    # ---- story ------------------------------------------------------------

    def _story(self, seeds, raw_edges, order, labels) -> list[str]:
        """The seed's flows in, its flows out, its downstream blast radius,
        and one sentence per loop."""
        incoming: dict[str, list[dict]] = {}
        outgoing: dict[str, list[dict]] = {}
        for edge in sorted(raw_edges, key=lambda e: (e["src_file"], e["dst_file"])):
            outgoing.setdefault(edge["src_file"], []).append(edge)
            incoming.setdefault(edge["dst_file"], []).append(edge)

        story: list[str] = []
        for seed in sorted(s for s in seeds if s in labels):
            name = labels[seed]
            for edge in incoming.get(seed, []):
                story.append(f"{labels[edge['src_file']]} -> "
                             f"{', '.join(edge['tables'])} -> {name}")
            for edge in outgoing.get(seed, []):
                story.append(f"{name} -> {', '.join(edge['tables'])} -> "
                             f"{labels[edge['dst_file']]}")
            downstream = self._downstream(seed, outgoing)
            names = ", ".join(labels.get(d, d) for d in downstream) or "none"
            story.append(f"if {name} changes, {len(downstream)} downstream "
                         f"files are affected: {names}")

        seen: set[str] = set()
        for fileid in sorted(order):
            result = order[fileid]
            if not result.cyclic or result.cycle_id in seen:
                continue
            seen.add(result.cycle_id)
            members = [labels.get(m, m) for m in result.cycle_members]
            sentence = (f"in a loop: {' -> '.join(members + members[:1])}; "
                        "data feeds back into where it started")
            if result.break_suggestion:
                src, dst = result.break_suggestion
                sentence += (f"; break the flow {labels.get(src, src)} -> "
                             f"{labels.get(dst, dst)} to serialize")
            story.append(sentence)
        return story

    @staticmethod
    def _downstream(seed: str, outgoing: dict[str, list[dict]]) -> list[str]:
        """Every file the seed's data reaches, transitively (seed excluded)."""
        reached: set[str] = set()
        queue = [seed]
        while queue:
            node = queue.pop(0)
            for edge in outgoing.get(node, []):
                if edge["dst_file"] not in reached:
                    reached.add(edge["dst_file"])
                    queue.append(edge["dst_file"])
        reached.discard(seed)
        return sorted(reached)

    # ---- file list --------------------------------------------------------

    @_serialized
    def list_files(self) -> list[dict]:
        """Every indexed file, as the explorer's ALL FILES layer draws it:
        ``{"id": fileid, "label": name, "folder": folder}``, sorted by id.

        This runs under the service lock like every other store-touching call
        — see `_serialized`. It is not optional here: the explorer asks for
        this list on the screen's very first paint, while the grid's
        whole-view Arrow load is already running on the SAME DuckDB
        connection, and an unlocked read there comes back holding the other
        query's rows.
        """
        rows = self.store.con.execute(
            "SELECT fileid, sasfilename, folder_path FROM files "
            "ORDER BY fileid").fetchall()
        return [{"id": fileid, "label": name, "folder": folder or ""}
                for fileid, name, folder in rows]

    # ---- file detail ------------------------------------------------------

    @_serialized
    def file_detail(self, fileid: str) -> dict:
        """One file's source, blocks, and its block/file edges with the
        provenance each level carries.

        Every block also carries a 1-based `line_start` into `code`, so the
        browser can scroll straight to it (see `block_line_starts`). It is
        added here, not in `sas_lineage.ui_export.build_file_entry`, because
        that builder is shared with the static HTML report — the parse stays
        untouched and the fresh dicts leave the cached entry alone.
        """
        resolved = self._resolve_file(fileid)
        if not resolved:
            raise FileNotFoundError(f"no such file: {fileid}")
        entry = self._entry(resolved[0])
        self._ensure_ingested([entry["fileid"]])
        starts = block_line_starts(entry["code"],
                                   [b["id"] for b in entry["blocks"]])
        total_lines = len(entry["code"].split("\n"))
        # inclusive 1-based ranges: a block runs to the line before the next
        # block's header (best-effort, like line_start itself)
        ends = [max(start, next_start - 1) for start, next_start
                in zip(starts, [*starts[1:], total_lines + 1])]
        if ends:
            ends[-1] = max(ends[-1], starts[-1])
        freshness = self._edge_freshness_of(entry["fileid"])
        return {
            "fileid": entry["fileid"],
            "name": entry["name"],
            "folder": entry["folder"],
            "code": entry["code"],
            "blocks": [{**block, "line_start": start, "line_end": end}
                       for block, start, end
                       in zip(entry["blocks"], starts, ends)],
            "block_edges": [
                {**_detail_edge(r, "block", "fact"),
                 "freshness": freshness.get(
                     (r["src_name"], r["dst_name"], "block"), "green")}
                for r in entry["block_edges"]],
            "file_edges": [
                {**_detail_edge(r, "file", "inferred"),
                 "freshness": freshness.get(
                     (r["src_name"], r["dst_name"], "file"), "green")}
                for r in entry["file_edges"]],
            "macro_calls": entry["macro_calls"],
            "includes": entry["includes"],
            "missing_includes": entry["missing_includes"],
        }

    def block_links(self, fileids: list[str]) -> list[dict]:
        """Cross-file block->block links for exactly the given files, computed
        from in-memory entries (same source as neighborhood/project edges)."""
        resolved = sorted({r for f in fileids for r in self._resolve_file(f)})
        if not resolved:
            return []
        entries = self._entries_for(resolved[:MAX_NEIGHBORHOOD])
        return project_edges_blocks(entries)

    def _edge_freshness_of(self, fileid: str) -> dict:
        """(src, dst, level) -> freshness for this file's stored engine
        rows — the graph tints stale extractions without a second parse."""
        return {
            (src, dst, "block" if edge_type == "BLOCK_FLOW" else "file"):
                freshness or "green"
            for src, dst, edge_type, freshness in self.store.con.execute(
                "SELECT source_canonical_name, target_canonical_name, "
                "edge_type, freshness FROM lineage WHERE fileid = ?",
                [fileid]).fetchall()
        }

    # ---- excel ------------------------------------------------------------

    @_serialized
    def excel_bytes(self, fileids: list[str]) -> bytes:
        """One workbook, three sheets: `provided` (what the tool produced),
        `customer_changes` (what a human asserted), and `final_edges` (the
        two merged — see `final_edges`), written write-only so a
        multi-million-row merge streams straight to the file instead of
        living as a Python list first."""
        entries = self._entries_for(fileids)
        resolved = [e["fileid"] for e in entries]
        self._ensure_ingested(resolved)

        book = Workbook(write_only=True)

        provided = book.create_sheet("provided")
        provided.append(PROVIDED_COLUMNS)
        for row in self._lineage_rows(resolved):
            provided.append(row)
        for row in self._project_rows(entries):
            provided.append(row)

        changes = book.create_sheet("customer_changes")
        changes.append(CHANGE_COLUMNS)
        for row in self.store.con.execute(
                f"SELECT {', '.join(CHANGE_COLUMNS)} FROM human_edits "
                "ORDER BY edited_at, edit_id").fetchall():
            changes.append([_cell(v) for v in row])

        final = book.create_sheet("final_edges")
        final.append(FINAL_EDGE_COLUMNS)
        self._stream_final_edges(final, resolved, entries)

        buffer = io.BytesIO()
        book.save(buffer)
        return buffer.getvalue()

    def _stream_final_edges(self, sheet, resolved: list[str],
                             entries: list[dict]) -> None:
        """Row-by-row `final_edges` merge -> the `final_edges` sheet. The
        merge itself is one DuckDB SQL statement (`_merged_edges`); only the
        write to xlsx is a Python loop, and it never holds the whole result
        set in memory at once."""
        self._materialize_provided(resolved, entries)
        cursor = self.store.con.execute(
            "SELECT src, dst, table_name, level, provenance, fileid, "
            "block_id FROM _merged_edges ORDER BY src, dst, table_name")
        written = 0
        while True:
            batch = cursor.fetchmany(1000)
            if not batch:
                return
            for src, dst, table_name, level, provenance, fileid, block_id \
                    in batch:
                if written >= MAX_XLSX_ROWS:
                    sheet.append(["TRUNCATED — scope the download",
                                 "", "", "", "", ""])
                    return
                sheet.append([src, dst, table_name, level, provenance,
                             _hyperlink(fileid, block_id)])
                written += 1

    def _lineage_rows(self, fileids: list[str]) -> list[list]:
        """Stored BLOCK_FLOW / FILE_FLOW rows, each tagged with provenance."""
        if not fileids:
            return []
        placeholders = ", ".join("?" for _ in fileids)
        rows = self.store.con.execute(
            f"SELECT {', '.join(COLUMNS)}, edge_type FROM lineage "
            f"WHERE fileid IN ({placeholders}) "
            "ORDER BY fileid, block_id, source_ref_id, target_ref_id",
            fileids).fetchall()
        return [
            [*(_cell(v) for v in row[:-1]), row[-1],
             PROVENANCE_BY_EDGE_TYPE.get(row[-1], "inferred")]
            for row in rows
        ]

    @staticmethod
    def _project_rows(entries: list[dict]) -> list[list]:
        """Cross-file flows in the same fixed shape, one row per table moved.

        Read a row as: inside `fileid`, data flows
        `source_canonical_name -> target_canonical_name` — a table into the
        file that reads it. The occurrence/ref columns stay empty because a
        project edge has no single block behind it.
        """
        rows = []
        for edge in project_edges(entries):
            for table in edge["tables"]:
                row = dict.fromkeys(COLUMNS, "")
                row["fileid"] = edge["src_file"]
                row["source_canonical_name"] = table
                row["target_canonical_name"] = edge["dst_file"]
                row["source_db_schema"] = schema_of(table)
                rows.append([row[c] for c in COLUMNS]
                            + ["PROJECT_FLOW", "inferred"])
        return rows

    # ---- customer edits ---------------------------------------------------

    @_serialized
    def add_edit(self, action, src, dst, table_name, level, editor,
                 comment="", block_id=None, fileid=None) -> str:
        """Record a HUMAN_GOLD assertion about the flow `src -> dst`. Never
        overwrites a tool row — it lands in its own table.

        `block_id` pins a block-level edit to the block it was made against
        (a project-level edit, with no single block behind it, leaves this
        `None`), and `fileid` names the file that block lives in: a block id
        is only unique WITHIN a file, so a block-level edit needs both.
        File- and project-level edits may leave `fileid` `None`.

        Re-confirming the SAME `src -> dst` / `table_name` / `level` flow
        (action `confirm`) clears `requires_check` on every earlier edit for
        that flow: this is how a human tells the tool "yes, this still holds
        against the new block text" after a re-parse flagged it stale.
        """
        if action not in ACTIONS:
            raise ValueError(
                f"unknown action {action!r}; expected one of "
                f"{', '.join(ACTIONS)}")
        # any human verdict on a flow settles its ghost: reject says "yes,
        # it is gone", confirm/add/correct re-assert it
        self.store.con.execute(
            "DELETE FROM lost_flows WHERE src = ? AND dst = ? "
            "AND table_name = ? AND level = ?",
            [src, dst, table_name, level])
        if action == "confirm":
            self.store.con.execute(
                "UPDATE human_edits SET requires_check = FALSE WHERE "
                "src = ? AND dst = ? AND table_name = ? AND level = ? "
                "AND requires_check",
                [src, dst, table_name, level])
        if action == "reject":
            # a discard: flagged twins of this flow leave the review queue
            # but stay requires_check, so they never re-enter the merge
            self.store.con.execute(
                "UPDATE human_edits SET dismissed = TRUE WHERE "
                "src = ? AND dst = ? AND table_name = ? AND level = ? "
                "AND requires_check",
                [src, dst, table_name, level])
        edit_id = uuid4().hex
        self.store.con.execute(
            "INSERT INTO human_edits (edit_id, edited_at, editor, action, "
            "src, dst, table_name, level, comment, block_id, fileid, "
            "requires_check) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)",
            [edit_id, datetime.now(), editor, action, src, dst, table_name,
             level, comment, block_id, fileid])
        return edit_id

    # ---- code save + timeline ----------------------------------------------

    def _engine_flow_lines(self, fileid: str) -> list[dict]:
        """The file's engine flows as logical identities (src, dst, table,
        level) — deliberately WITHOUT block ids, so a block whose id moved
        but whose flow survived does not show up as an edge change. Project
        rows are excluded: they depend on other files, and this is one
        file's own timeline."""
        rows = self.store.con.execute(
            "SELECT DISTINCT source_canonical_name, target_canonical_name, "
            "CASE edge_type WHEN 'BLOCK_FLOW' THEN 'block' ELSE 'file' END "
            "FROM lineage WHERE fileid = ? ORDER BY 1, 2, 3",
            [fileid]).fetchall()
        return [{"src": s, "dst": d, "table_name": s, "level": lvl}
                for s, d, lvl in rows]

    @_serialized
    def save_code(self, fileid: str, code: str, editor: str,
                  reason: str) -> dict:
        """Write edited SAS back to the estate and commit it (with the
        file's engine flows) to the shadow repo — author = editor,
        message = reason. The first save of a file seeds the repo with the
        pre-edit state, so the timeline always starts at "original import".
        Returns the flow delta the save caused (`added` / `removed`)."""
        if self.history is None:
            raise ValueError("code saving is disabled: no history repo")
        if not editor.strip() or not reason.strip():
            raise ValueError("editor and reason are both required")
        path = self._path_for(fileid)
        old_code = path.read_text(errors="ignore")

        self._ensure_ingested([fileid])          # engine rows for OLD bytes
        old_edges = self._engine_flow_lines(fileid)
        if not self.history.has_file(fileid):
            self.history.record(fileid, old_code, old_edges,
                                "engine", "original import")

        path.write_text(code)
        self._ensure_ingested([fileid])          # re-parse + flag stale edits
        new_edges = self._engine_flow_lines(fileid)
        commit = self.history.record(fileid, code, new_edges, editor, reason)

        old_keys = {json.dumps(e, sort_keys=True) for e in old_edges}
        new_keys = {json.dumps(e, sort_keys=True) for e in new_edges}
        return {
            "commit": commit,
            "saved_at": datetime.now().isoformat(),
            "added": [json.loads(s) for s in sorted(new_keys - old_keys)],
            "removed": [json.loads(s) for s in sorted(old_keys - new_keys)],
        }

    @_serialized
    def pending_checks(self) -> list[dict]:
        """Human edits flagged `requires_check`: each points at a block id
        the latest parse of its file no longer has, and is queued for a
        person to review — re-confirm it against the new block, or reject
        it."""
        columns = ["edit_id", "edited_at", "editor", "action", "src", "dst",
                   "table_name", "level", "comment", "block_id", "fileid"]
        rows = self.store.con.execute(
            f"SELECT {', '.join(columns)} FROM human_edits "
            "WHERE requires_check AND NOT dismissed "
            "ORDER BY edited_at, edit_id").fetchall()
        return [dict(zip(columns, (_cell(v) for v in row))) for row in rows]

    # ---- final edges --------------------------------------------------------

    @_serialized
    def final_edges(self, fileids: list[str] | None = None, *,
                     filter_text: str | None = None, level: str | None = None,
                     offset: int = 0,
                     limit: int = DEFAULT_EDGES_LIMIT) -> dict:
        """The merged view, one page of it: engine block/file/project rows
        with un-flagged customer edits applied — `reject` drops the matching
        block's rows, `confirm` upgrades their provenance to `human_gold`,
        `add` appends a new `human_gold` row. An edit still `requires_check`
        is skipped, as if it did not exist, until a human re-confirms it
        (see `add_edit`).

        The merge is one DuckDB SQL statement (`_merged_edges`, built by
        `_materialize_provided`) — filtering, counting and paging are all
        plain SQL over it; nothing here loops row by row in Python.

        `correct` merges exactly like `add`: the corrected flow appears as a
        new `human_gold` row and the engine's own row is LEFT ALONE. A
        correction is a person saying "this is the flow the code really
        has", not "delete what you found" — the engine row stays visible so
        the two can be compared side by side, and `reject` remains the one
        action that removes a row.

        Returns ``{"total": <rows matching filter/level>, "rows": [...]}``.
        """
        entries = self._entries_for(fileids or self._all_fileids())
        resolved = [e["fileid"] for e in entries]
        self._ensure_ingested(resolved)
        self._materialize_provided(resolved, entries)

        where_sql, params = self._edges_where(filter_text, level)
        total = self.store.con.execute(
            f"SELECT count(*) FROM _merged_edges WHERE {where_sql}",
            params).fetchone()[0]
        rows = self.store.con.execute(
            "SELECT fileid, block_id, src, dst, table_name, level, "
            f"provenance, freshness FROM _merged_edges WHERE {where_sql} "
            "ORDER BY src, dst, table_name LIMIT ? OFFSET ?",
            [*params, limit, offset]).fetchall()
        # the JSON shape matches every other edge the API returns
        # (Neighborhood.edges, FileDetail.block_edges/file_edges): `tables`
        # is a list, even though a merged-edge row is always one table — so
        # the web client's single `EdgeOut` type covers every edge source.
        return {"total": total, "rows": [
            {"fileid": fileid, "block_id": block_id, "src": src, "dst": dst,
             "tables": [table_name], "level": lvl, "provenance": provenance,
             "freshness": freshness}
            for fileid, block_id, src, dst, table_name, lvl, provenance,
                freshness in rows]}

    def _all_fileids(self) -> list[str]:
        return [r[0] for r in self.store.con.execute(
            "SELECT DISTINCT fileid FROM files ORDER BY fileid").fetchall()]

    # ---- arrow (the grid IS the Excel) --------------------------------------

    @_serialized
    def edges_arrow(self, fileids: list[str] | None = None, *,
                     view: str = "final") -> bytes:
        """One whole view of the edges as an Apache Arrow IPC stream.

        This is the payload behind "load everything, no pagination": DuckDB
        builds the columnar result, pyarrow serializes it as-is, and the
        browser holds it as typed columns — so filtering and sorting are
        local array scans instead of round-trips. `final_edges` stays for
        the paged JSON grid; both read the same merge.
        """
        return serialize_arrow_stream(self.edges_arrow_reader(fileids,
                                                              view=view))

    @_serialized
    def edges_arrow_table(self, fileids: list[str] | None = None, *,
                           view: str = "final") -> "pa.Table":
        """`edges_arrow`'s rows as one in-memory Arrow table (the streamed
        payload, materialized) — handy for callers that want to look at the
        result instead of shipping it."""
        return self.edges_arrow_reader(fileids, view=view).read_all()

    @_serialized
    def edges_arrow_reader(self, fileids: list[str] | None = None, *,
                            view: str = "final") -> "pa.RecordBatchReader":
        """DuckDB's own record batches for a view, in `EDGE_ARROW_COLUMNS`
        order — batch by batch, so a multi-million-row view is serialized as
        it is produced instead of being held whole first.

        - `engine` — `_provided_edges`: the latest parse only. A customer
          edit never touches it, so `requires_check` is always FALSE here.
        - `human` — the `human_edits` rows themselves (every one of them
          human_gold), carrying `requires_check` so the grid can raise the
          "this block moved, please re-check" queue in amber.
        - `final` — `_merged_edges`: the engine rows with the un-flagged
          customer edits applied.

        The `human` view is deliberately NOT scoped by `fileids`: a customer
        edit is keyed by the flow it asserts (`src -> dst` / table / level),
        which for a block-level edit is a pair of table names — there is no
        fileid to filter it by without dropping rows a person entered.
        """
        if view not in ARROW_VIEWS:
            raise ValueError(
                f"unknown view {view!r}; expected one of "
                f"{', '.join(ARROW_VIEWS)}")
        if view == "human":
            # an edit may name no file at all (file/project level), but the
            # column contract says `fileid` is never NULL — '' reads as
            # "this edit is not pinned to one file"
            return _as_reader(self.store.con.execute(
                "SELECT COALESCE(fileid, '') AS fileid, src, dst, "
                "table_name, level, 'human_gold' AS provenance, block_id, "
                "COALESCE(requires_check, FALSE) AS requires_check, "
                "COALESCE(freshness, 'green') AS freshness "
                "FROM human_edits "
                "ORDER BY src, dst, table_name, edited_at, edit_id").arrow())

        entries = self._entries_for(fileids or self._all_fileids())
        resolved = [e["fileid"] for e in entries]
        self._ensure_ingested(resolved)
        self._materialize_provided(resolved, entries)
        # ghost rows — flows a previous parse had that the newest one lost —
        # ride along ONLY here (never in Excel or the paged JSON merge);
        # red sorts first because it is the review queue
        source = "_provided_edges" if view == "engine" else "_merged_edges"
        return _as_reader(self.store.con.execute(f"""
            SELECT * FROM (
                SELECT fileid, src, dst, table_name, level, provenance,
                       block_id, FALSE AS requires_check, freshness
                FROM {source}
                UNION ALL
                SELECT fileid, src, dst, table_name, level,
                       CASE level WHEN 'block' THEN 'fact'
                            ELSE 'inferred' END AS provenance,
                       block_id, FALSE AS requires_check, 'red' AS freshness
                FROM lost_flows
                WHERE fileid IN (SELECT fileid FROM _scope_fileids)
            )
            ORDER BY CASE freshness WHEN 'red' THEN 0
                          WHEN 'yellow' THEN 1 ELSE 2 END,
                     src, dst, table_name
            """).arrow())

    @staticmethod
    def _edges_where(filter_text: str | None,
                      level: str | None) -> tuple[str, list]:
        """WHERE clause + params for a text/level filter over
        `_merged_edges` (src, dst, table_name, level columns)."""
        clauses, params = [], []
        if filter_text and filter_text.strip():
            pattern = f"%{filter_text.strip().lower()}%"
            clauses.append("(lower(src) LIKE ? OR lower(dst) LIKE ? "
                           "OR lower(table_name) LIKE ?)")
            params += [pattern, pattern, pattern]
        if level:
            clauses.append("level = ?")
            params.append(level)
        return (" AND ".join(clauses) if clauses else "TRUE"), params

    def _materialize_provided(self, resolved: list[str],
                               entries: list[dict]) -> None:
        """(Re)builds the two temp views this session's queries read from:
        `_provided_edges` (the engine view — block/file rows from `lineage`
        unioned with the project-level rows computed here, which are
        parse-on-demand and so never land in `lineage`) and `_merged_edges`
        (the final view — `_provided_edges` merged against `human_edits` in
        one SQL statement): reject drops a block's rows, confirm upgrades
        their provenance, add/correct append a `human_gold` row, and any edit
        still `requires_check` is ignored entirely."""
        # DuckDB's DDL statements (CREATE VIEW/TABLE) cannot take prepared
        # parameters, so the fileid scope and the project edges are staged
        # into their own temp tables first (parameterized INSERTs, safe
        # against any character a path can contain) and the merge view
        # below joins/filters against those tables instead of inlining
        # values into the SQL text.
        self.store.con.execute(
            "CREATE OR REPLACE TEMP TABLE _scope_fileids (fileid VARCHAR)")
        if resolved:
            self.store.con.executemany(
                "INSERT INTO _scope_fileids VALUES (?)",
                [(f,) for f in resolved])

        self.store.con.execute(
            "CREATE OR REPLACE TEMP TABLE _project_edges "
            "(fileid VARCHAR, block_id VARCHAR, src VARCHAR, dst VARCHAR, "
            "table_name VARCHAR, level VARCHAR, provenance VARCHAR)")
        project_rows = [
            (edge["src_file"], None, edge["src_file"], edge["dst_file"],
             table, "project", "inferred")
            for edge in project_edges(entries) for table in edge["tables"]
        ]
        if project_rows:
            self.store.con.executemany(
                "INSERT INTO _project_edges VALUES (?, ?, ?, ?, ?, ?, ?)",
                project_rows)

        # the engine view: exactly what the latest parse says, nothing merged
        self.store.con.execute("""
            CREATE OR REPLACE TEMP VIEW _provided_edges AS
            SELECT fileid, block_id, source_canonical_name AS src,
                   target_canonical_name AS dst,
                   source_canonical_name AS table_name,
                   CASE edge_type WHEN 'BLOCK_FLOW' THEN 'block'
                        ELSE 'file' END AS level,
                   CASE edge_type WHEN 'BLOCK_FLOW' THEN 'fact'
                        ELSE 'inferred' END AS provenance,
                   COALESCE(freshness, 'green') AS freshness
            FROM lineage
            WHERE fileid IN (SELECT fileid FROM _scope_fileids)
            UNION ALL
            SELECT fileid, block_id, src, dst, table_name, level, provenance,
                   'green' AS freshness
            FROM _project_edges
        """)

        self.store.con.execute("""
            CREATE OR REPLACE TEMP VIEW _merged_edges AS
            WITH provided AS (
                SELECT fileid, block_id, src, dst, table_name, level,
                       provenance, freshness
                FROM _provided_edges
            ),
            rejected AS (
                SELECT DISTINCT fileid, block_id FROM human_edits
                WHERE action = 'reject' AND NOT requires_check
                  AND block_id IS NOT NULL
            ),
            confirmed AS (
                SELECT DISTINCT fileid, block_id FROM human_edits
                WHERE action = 'confirm' AND NOT requires_check
                  AND block_id IS NOT NULL
            )
            SELECT fileid, block_id, src, dst, table_name, level,
                   CASE WHEN EXISTS (
                       SELECT 1 FROM confirmed c
                       WHERE c.block_id = provided.block_id
                         AND (c.fileid IS NULL OR c.fileid = provided.fileid)
                   ) THEN 'human_gold' ELSE provenance END AS provenance,
                   freshness
            FROM provided
            WHERE block_id IS NULL
               OR NOT EXISTS (
                   SELECT 1 FROM rejected r
                   WHERE r.block_id = provided.block_id
                     AND (r.fileid IS NULL OR r.fileid = provided.fileid)
               )
            UNION ALL
            SELECT COALESCE(fileid, src) AS fileid, block_id, src, dst,
                   table_name, level, 'human_gold' AS provenance,
                   'green' AS freshness
            FROM human_edits
            WHERE action IN ('add', 'correct') AND NOT requires_check
        """)
