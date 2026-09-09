"""Incremental search index over the SAS tree, backed by the existing DuckDB
store.

Two things live here on top of `sas_lineage.store.LineageStore`:

  mentions      one row per (term, fileid): a cheap, comment-stripped regex
                scan for `libref.name`-shaped tokens (this is NOT the full
                parse — that happens on demand in service.py). Drives
                typeahead and "which files mention this table".
  human_edits   customer confirm/reject/add edits on flows (HUMAN_GOLD);
                created here so the schema exists before service.py needs it.
                `block_id` pins a block-level edit to the block it was made
                against; `fileid` names the file that block lives in (a block
                id is only unique WITHIN a file, so a block-level edit needs
                both); `requires_check` is TRUE when a re-parse made that
                block id vanish (see `flag_stale_edits`).

`build()` walks the configured roots for `*.sas` files (sorted, deterministic)
and skips any file whose content hash has not changed since the last build
(hash-skip index). Only changed/new files pay for `_cheap_scan`.

A `fileid` is the file's path relative to `common_base(roots)` — stable, so
an edited file keeps its id and only `files.sashashcode` moves. That is what
makes "has this changed?" a hash question and never an identity question.

An `ahocorasick.Automaton` over every distinct known term is rebuilt at the
end of each `build()` call, for fast substring/typeahead matching later.
"""
import re
import threading
from datetime import datetime
from functools import wraps
from pathlib import Path

import ahocorasick

from sas_lineage.exporter import make_fileid, relative_folder
from sas_lineage.registry import file_hash
from sas_lineage.scanner import strip_comments
from sas_lineage.store import LineageStore

TERM_RE = re.compile(r"[A-Za-z_]\w*\.[A-Za-z_]\w*")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mentions (
    term VARCHAR, fileid VARCHAR, path VARCHAR, PRIMARY KEY (term, fileid));
CREATE TABLE IF NOT EXISTS human_edits (
    edit_id VARCHAR PRIMARY KEY, edited_at TIMESTAMP, editor VARCHAR,
    action VARCHAR, src VARCHAR, dst VARCHAR, table_name VARCHAR,
    level VARCHAR, comment VARCHAR);
ALTER TABLE human_edits ADD COLUMN IF NOT EXISTS block_id VARCHAR;
ALTER TABLE human_edits ADD COLUMN IF NOT EXISTS requires_check BOOLEAN DEFAULT FALSE;
ALTER TABLE human_edits ADD COLUMN IF NOT EXISTS fileid VARCHAR;
ALTER TABLE human_edits ADD COLUMN IF NOT EXISTS dismissed BOOLEAN DEFAULT FALSE;
ALTER TABLE human_edits ADD COLUMN IF NOT EXISTS freshness VARCHAR DEFAULT 'green';
"""

_SUGGEST_LIMIT = 20

#: how many candidates each suggest query gathers BEFORE ranking — an
#: alphabetical LIMIT alone would cut good hits before ranking ever saw them
_SUGGEST_CANDIDATES = 200


def common_base(roots: list[Path]) -> Path | None:
    """The one folder every root sits under — the base both `fileid` and
    `folder_path` are measured from, so the indexer and the service always
    mint the SAME id for the same file. `None` when the roots share nothing
    (then each file falls back to its own parent folder)."""
    roots = [Path(r) for r in roots]
    if not roots:
        return None
    if len(roots) == 1:
        return roots[0].resolve()
    common = []
    for parts in zip(*[r.resolve().parts for r in roots]):
        if len(set(parts)) != 1:
            break
        common.append(parts[0])
    return Path(*common) if common else None


def _serialized(method):
    """Run this call while holding the lock that guards the DuckDB connection.

    The `Indexer` and the `Service` share ONE store, so they share ONE
    connection — and both read it while requests are in flight: the indexer
    answers the typeahead (`suggest`) and the status bar (`_tables_known`)
    while the service is streaming a whole edge view out of the same
    connection. Unguarded, such a read comes back holding the OTHER query's
    rows. `Service` adopts this very lock (see `Service.__init__`), so the
    two never collide; it is reentrant, so these methods can call each other.
    """
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return wrapper


class Indexer:
    def __init__(self, store: LineageStore, roots: list[Path]):
        self.store = store
        self.roots = [Path(r) for r in roots]
        self.base_dir = common_base(self.roots)
        self.progress = {"state": "building", "done": 0, "total": 0}
        #: the one lock over the one connection — the Service adopts it
        self.lock = threading.RLock()
        for statement in _SCHEMA.strip().split(";"):
            if statement.strip():
                self.store.con.execute(statement)
        self.automaton = ahocorasick.Automaton()
        self.automaton.make_automaton()

    # ---- build ----------------------------------------------------------

    def build(self) -> dict:
        self.progress = {"state": "building", "done": 0, "total": 0}
        paths = sorted(
            {p for root in self.roots for p in Path(root).rglob("*.sas")})
        self.progress["total"] = len(paths)

        # fileids are stable paths, so the previous hash is looked up by id
        # (the lock is taken per statement, never for the whole walk: a
        # 30,000-file build must not block the screen for its duration)
        with self.lock:
            existing = dict(self.store.con.execute(
                "SELECT fileid, sashashcode FROM files").fetchall())

        files_indexed = 0
        for done, path in enumerate(paths, start=1):
            fileid = make_fileid(path, self.base_dir)
            new_hash = file_hash(path.read_text(errors="ignore"))
            if existing.get(fileid) == new_hash:
                self.progress["done"] = done
                continue

            folder = relative_folder(path, self.base_dir)
            terms = self._cheap_scan(path)
            with self.lock:   # one file's rows land together
                self._upsert_file(fileid, path.name, folder, new_hash)
                self._replace_mentions(fileid, str(path), terms)
            files_indexed += 1
            self.progress["done"] = done

        self._rebuild_automaton()
        self.progress["state"] = "ready"
        return {
            "files_total": len(paths),
            "files_indexed": files_indexed,
            "tables_known": self._tables_known(),
        }

    def _cheap_scan(self, path: Path) -> set[str]:
        text = Path(path).read_text(errors="ignore")
        stripped = strip_comments(text)
        return {m.group(0).lower() for m in TERM_RE.finditer(stripped)}

    @_serialized
    def _upsert_file(self, fileid, sasfilename, folder, sashashcode):
        self.store.con.execute("DELETE FROM files WHERE fileid = ?", [fileid])
        self.store.con.execute(
            "INSERT INTO files (fileid, sasfilename, folder_path, "
            "sashashcode, analyzed_at) VALUES (?, ?, ?, ?, ?)",
            [fileid, sasfilename, folder, sashashcode,
             datetime.now().isoformat(sep=" ", timespec="seconds")])

    @_serialized
    def _replace_mentions(self, fileid, path_str, terms):
        self.store.con.execute("DELETE FROM mentions WHERE fileid = ?", [fileid])
        if terms:
            self.store.con.executemany(
                "INSERT INTO mentions (term, fileid, path) VALUES (?, ?, ?)",
                sorted((term, fileid, path_str) for term in terms))

    @_serialized
    def _tables_known(self) -> int:
        return self.store.con.execute(
            "SELECT count(DISTINCT term) FROM mentions").fetchone()[0]

    @_serialized
    def _rebuild_automaton(self):
        automaton = ahocorasick.Automaton()
        rows = self.store.con.execute(
            "SELECT DISTINCT term FROM mentions ORDER BY term").fetchall()
        for (term,) in rows:
            automaton.add_word(term, term)
        automaton.make_automaton()
        self.automaton = automaton

    # ---- edit lifecycle -----------------------------------------------------

    @_serialized
    def flag_stale_edits(self, fileid: str) -> None:
        """After `fileid` was (re-)ingested, color its block-level edits:

            green   the edit's block id is still in the latest parse
            yellow  block gone, but the flow `src -> dst` survived the
                    re-parse — the confirmation stays valid (kept, not
                    flagged)
            red     block gone AND flow gone — queued for review
                    (`requires_check`), so a customer note never silently
                    vanishes just because the code moved

        Edits with no `block_id` (project-level, keyed by file names only)
        are untouched. Legacy rows that stored the fileid in `src` (before
        the `fileid` column existed) are matched by that convention too.
        """
        self.store.con.execute(
            """
            UPDATE human_edits SET
                freshness = CASE
                    WHEN block_id IN (SELECT block_id FROM blocks
                                      WHERE fileid = ?) THEN 'green'
                    WHEN EXISTS (SELECT 1 FROM lineage l WHERE l.fileid = ?
                                 AND l.source_canonical_name = human_edits.src
                                 AND l.target_canonical_name = human_edits.dst)
                        THEN 'yellow'
                    ELSE 'red' END,
                requires_check = CASE
                    WHEN block_id IN (SELECT block_id FROM blocks
                                      WHERE fileid = ?) THEN requires_check
                    WHEN EXISTS (SELECT 1 FROM lineage l WHERE l.fileid = ?
                                 AND l.source_canonical_name = human_edits.src
                                 AND l.target_canonical_name = human_edits.dst)
                        THEN requires_check
                    ELSE TRUE END
            WHERE block_id IS NOT NULL
              AND (fileid = ? OR (fileid IS NULL AND src = ?))
            """,
            [fileid] * 6)

    # ---- read -------------------------------------------------------------

    @_serialized
    def files_mentioning(self, term: str) -> list[str]:
        term = term.strip().lower()
        rows = self.store.con.execute(
            "SELECT DISTINCT fileid FROM mentions WHERE term = ? "
            "ORDER BY fileid", [term]).fetchall()
        return [r[0] for r in rows]

    @_serialized
    def suggest(self, q: str) -> list[dict]:
        """Typeahead hits, most useful first.

        Ranked, not alphabetical: exact match, then prefix, then substring;
        ties break to the hit mentioned in more files. Terms whose qualifier
        is a single letter (``a.cust_id``) are almost always SQL-alias column
        refs the cheap ``x.y`` scan picked up, not tables — they are demoted
        below every real hit rather than dropped, since a one-letter libref
        is legal SAS."""
        q = q.strip().lower()
        if not q:
            return []
        pattern = f"%{q}%"
        hits = []

        term_rows = self.store.con.execute(
            "SELECT DISTINCT term FROM mentions WHERE term LIKE ? "
            "ORDER BY term LIMIT ?", [pattern, _SUGGEST_CANDIDATES]).fetchall()
        for (term,) in term_rows:
            files = [r[0] for r in self.store.con.execute(
                "SELECT DISTINCT fileid FROM mentions WHERE term = ? "
                "ORDER BY fileid", [term]).fetchall()]
            hits.append({"kind": "table", "value": term, "files": files})

        name_rows = self.store.con.execute(
            "SELECT DISTINCT sasfilename FROM files "
            "WHERE lower(sasfilename) LIKE ? ORDER BY sasfilename LIMIT ?",
            [pattern, _SUGGEST_CANDIDATES]).fetchall()
        for (name,) in name_rows:
            files = [r[0] for r in self.store.con.execute(
                "SELECT DISTINCT fileid FROM files WHERE sasfilename = ? "
                "ORDER BY fileid", [name]).fetchall()]
            hits.append({"kind": "file", "value": name, "files": files})

        def rank(hit):
            value = hit["value"].lower()
            alias = (1 if hit["kind"] == "table"
                     and len(value.split(".", 1)[0]) == 1 else 0)
            exactness = 0 if value == q else (1 if value.startswith(q) else 2)
            return (alias, exactness, -len(hit["files"]), hit["kind"], value)

        hits.sort(key=rank)
        return hits[:_SUGGEST_LIMIT]
