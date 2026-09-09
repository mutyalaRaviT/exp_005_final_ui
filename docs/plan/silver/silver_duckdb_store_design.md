---
tags: [plan, silver, duckdb, store, exp-005, verification]
---
# silver_duckdb_store_design — the DuckDB store for phase 1

**Why this file exists.** The owner said: *"Duckdb architecture is important, use the
`:5199/?file=ankitha_1%2F07_enrich_fx.sas&up=1&down=1` backend for design."* That backend is
`raw/lineage_server` on `:8000` over `explorer.duckdb`. This page derives the exp_005 store
from that working store, corrects the strawman in `backend/rust_inferred_duckdb/src/schema.rs`,
and adds what a real parser and the four-leg verification loop need.

**Inputs → outputs.** [[gold_three_uis_and_verification_loop]] (the authority), plan §5–§7 of
[[gold_draft_exp_005_plan]], [[bronze_perf_receipts_exp42]], [[bronze_local_run_2026-09-09]],
the live `:8000` API and its SQL (`server/service.py`, `server/indexer.py`,
`exp_2/sas_lineage/store.py`), a read-only copy of `explorer.duckdb`, and the strawman
**measured** on `big_1000.sas` → the DDL, the ten questions as SQL, the write path, the
verification tables, and a migration list for `schema.rs`.

---

## 0. Receipts first: what I measured on 2026-09-09

The strawman binary was already built (`backend/target/release/lineageq_store`). I ran it.

| measurement | value | pass mark |
|---|---|---|
| `convert` of `big_1000.sas` (1000 blocks, 3303 statements, 1204 edges), cold, fresh db | **1089 ms** = fold 526 + store 562 | < 3000 ms ✓ |
| second `convert`, file unchanged (hash skip) | 1 ms | — |
| `convert` again after appending one comment line (same PKs deleted and re-inserted in one transaction) | 1104 ms, no error | idempotent ✓ |
| `file(big_1000.sas)` — 1000 block heads, no text | **1.7 ms** cold, 0.39 ms warm; **85 KB** JSON | < 20 ms ✓ |
| `blocks(big_1000.sas, 0, 40)` | **1.05 ms**; 27 KB (21.8 KB of text) | < 20 ms ✓ |
| `blocks(big_1000.sas, 960, 1000)` | 0.98 ms | — |
| `search("t05")` | 0.5 ms, 50 hits | — |
| database file | 4.7 MB; text held: SAS 99 KB, PySpark 298 KB, pretty 417 KB, node/4 173 KB | — |
| DuckDB bundled by the `duckdb` crate (`libduckdb-sys 1.10505.0`) | **v1.5.5** | — |

**So phase 1's pass mark is already met by the strawman.** Speed is not the problem. The
problem is that the strawman stores the wrong things, and two of its receipts are made up
(§4). That is why this page exists.

---

## 1. What the working store actually does

Think of the store as a **library card catalogue**. `convert` writes the cards once. Every
question the UI asks is a card lookup — nobody re-reads the book. Human corrections are the
librarian's pencil notes: laid over the printed card, never erasing it.

Here is what `:8000` does behind each answer, read from `service.py`. Several of these were
surprises.

| `:8000` question | what really happens | tables touched |
|---|---|---|
| `/api/neighborhood` | **Not from `lineage`.** Seeds → `mentions` nominates candidate files per table → each candidate's in-memory parse (`_entry`) confirms it reads/writes the table → walk `up`/`down` hops → project edges computed in Python by `project_edges()` (writers × readers per table) → run order by `orderer.py`. `/api/status` says `scanner: rg, synced_at: null`: it answers from the ripgrep scan, not the synced store. | `mentions`, `files`; the parse cache |
| `/api/file/{id}` | parse cache again; `block_line_starts` guesses line ranges by regex; `freshness` per edge is the only thing read from `lineage`. Returns the **whole file's `code`**. | `lineage` |
| `/api/blocklinks` | `project_edges_blocks()` over in-memory entries: writer block → reader block across files, keyed by occurrence ids `b_1:t_3`. | none |
| `/api/edges?level=` | the **merged** view `_merged_edges`: engine rows ∪ human edits (§1.2). `level=project` rows are staged into a temp table per request, never stored. | `lineage`, `human_edits`, temp tables |
| `/api/search` | `SELECT DISTINCT term FROM mentions WHERE term LIKE '%q%'` + file names, ranked in Python (exact > prefix > substring; one-letter aliases like `a.cust_id` demoted). | `mentions`, `files` |
| `/api/edits` | insert into `human_edits`; `confirm` clears `requires_check`; `reject` sets `dismissed` on flagged twins. | `human_edits`, `lost_flows` |

### 1.1 The three levels are not three rows of one table

| level | `edge_type` | provenance | where it lives in `:8000` | rows in the copy |
|---|---|---|---|---|
| block | `BLOCK_FLOW` | `fact` — the source literally says it | stored in `lineage` | 41 |
| file | `FILE_FLOW` | `inferred` — block A writes T, a later block B in the same file reads T | stored in `lineage` | 1 |
| project | `PROJECT_FLOW` | `inferred` — file A writes T, file B reads T | **computed per request**, temp table `_project_edges` | 0 |

The `level` column exists only in the view `_provided_edges` (`CASE edge_type WHEN
'BLOCK_FLOW' THEN 'block' ELSE 'file' END`). The plan's "level: block | file | project" column
is the view, not the storage. In exp_005 the two inferred levels are **derived by SQL** from
the block facts (§3, questions 1, 2, 5). Only facts are stored.

### 1.2 How `human_edits` overlays the engine rows (the `HUMAN_GOLD` badge)

An edit is a row `(action, src, dst, table_name, level, fileid, block_id, requires_check,
dismissed, freshness)`. Four actions, and the merge in one SQL statement:

| action | effect in `_merged_edges` |
|---|---|
| `reject` | the engine rows of that `(fileid, block_id)` disappear |
| `confirm` | those rows stay, provenance becomes `human_gold` |
| `add` | a new `human_gold` row appears |
| `correct` | same as `add` — the engine row is **left in place** so the two can be compared |

`requires_check` and `dismissed` are the re-parse lifecycle (`indexer.flag_stale_edits`):

- after a file is re-ingested, an edit pinned to a `block_id` that is **gone** and whose flow
  `src -> dst` is **also gone** turns `red` and gets `requires_check = TRUE`. It is skipped by
  the merge until a human re-`confirm`s it (which clears the flag).
- block gone but the flow survived → `yellow`, still valid, not flagged.
- `dismissed = TRUE` is set by a later `reject` of the same flow: the flagged twins leave the
  review queue (`/api/edits/pending`) but stay `requires_check`, so they never re-enter the merge.

This only works because `:8000`'s block ids are **content-addressed**: `b_<ordinal>_<hash8>`,
hash of the block's own statements. A block whose text did not change keeps its id, and the
pencil note pinned to it survives. **The exp_005 engine's ids are positional (`b_017`)** —
insert one block above and every note below it points at the wrong block. §2 fixes this with a
`block_hash` column.

### 1.3 The rest of the `:8000` schema, in one line each

- `mentions(term, fileid, path)` — a cheap regex over `x.y` tokens, comments stripped. 185 rows,
  87 distinct terms, and many are SQL aliases, not tables. Its job: nominate files for the walk,
  and typeahead.
- `events(seq, ts, session_id, event_type, fileid, payload)` — the payload is the **whole write
  bundle as JSON**; `consolidate_sessions` / `recover` replay it. `seq` comes from a SEQUENCE so
  pruning never resets it.
- `folder_path` on `files`, `blocks`, `lineage` — used by `COPY … PARTITION_BY (folder_path)` in
  `export_parquet`, and by `list_files` for the label. Nothing else reads it.
- `sources(fileid, source)` — the raw text, "so search never needs the disk in production" (in
  the code, absent from the copy I had).
- `lost_flows` — ghost rows: flows a previous parse had and the new one lost, shown red.
- `macros`, `macro_calls` — modelled, 0 rows here; the `:8000` parser handles `%macro` and
  gives macro-instance blocks ids `<def_id>#<k>`.
- `lineage`'s fifteen columns — see §4 for which survive.

---

## 2. The tables

Thirteen tables and two views. The plan's eight are wrong in two places: `tables` goes (it is a
`GROUP BY` over `table_refs`), and the strawman's `edges` shape goes (it cannot say which block
made the edge — `block_id` is `''` on all 1204 rows of `big_1000`). Five come in: `table_refs`,
`human_edits`, `lineage_facts`, `run_tables` + `run_samples`, `testcases`. Column origins:
**[8000]** = copied from the working store (table named), **[bench]** = the Bench's block model,
**[new]** = the parser makes it necessary.

```sql
-- ------------------------------------------------------------------ files
CREATE TABLE IF NOT EXISTS files (
    fileid       VARCHAR PRIMARY KEY,  -- [8000 files] path relative to the folder; STABLE across edits
    name         VARCHAR NOT NULL,     -- [8000 files.sasfilename] the label UI1 draws
    folder       VARCHAR NOT NULL,     -- [8000 files.folder_path] kept HERE ONLY (§4); list_files and parquet export read it
    hash         VARCHAR NOT NULL,     -- [8000 files.sashashcode] FNV-1a of the bytes; half of the idempotence key
    rules_hash   VARCHAR NOT NULL,     -- [new] hash of sas.json + engine version; the other half. Strawman bug: a rules change never reconverted
    loc          INTEGER,              -- [8000 files.loc]
    status       VARCHAR NOT NULL,     -- [8000 files.conversion_status] converted | partial | error
    error        VARCHAR,              -- [new] the engine's message when status = error
    source       VARCHAR,              -- [8000 sources.source] whole text; read ONLY by source(fileid) for UI1's code pane, never by file()
    converted_at TIMESTAMP NOT NULL
);

-- ----------------------------------------------------------------- blocks
CREATE TABLE IF NOT EXISTS blocks (
    fileid     VARCHAR NOT NULL,
    block_id   VARCHAR NOT NULL,       -- [bench] the engine's positional id b_017; shared with node/4 and Prolog, so it stays
    n          INTEGER NOT NULL,       -- [bench] 0-based order; the window key
    block_hash VARCHAR NOT NULL,       -- [8000 blocks b_<n>_<hash8>] hash of the block's statements; what human_edits pin to (§1.2)
    kind       VARCHAR NOT NULL,       -- [bench] data | proc_sql | proc_print | libname …  (the first term's functor)
    name       VARCHAR,                -- [bench] the table this block writes, or NULL
    l0         INTEGER NOT NULL,       -- [bench] first line (1-based)
    l1         INTEGER NOT NULL,       -- [bench] last line
    n_stmts    INTEGER NOT NULL,       -- [new] statements folded into this block; file() shows it without touching node4
    sas_text   VARCHAR NOT NULL,       -- [bench] lines l0..l1 of the source
    py_text    VARCHAR NOT NULL,       -- [bench] PySpark from node/4 (runnable form)
    py_pretty  VARCHAR NOT NULL,       -- [bench] the readable form; what the cell shows
    warn       VARCHAR,                -- [bench] the LINEAGEQ CHECK / WARNING line the emitter left, or NULL (strawman had BOOLEAN, always false)
    PRIMARY KEY (fileid, block_id)
);

-- ------------------------------------------------------------------ node4
-- one row per node/4 term. The .node4.pl file Prolog reads is regenerated from this table,
-- byte for byte, so the trace needs all five fields of trace(File,L0,L1,B0,B1).
CREATE TABLE IF NOT EXISTS node4 (
    fileid       VARCHAR NOT NULL,
    block_id     VARCHAR NOT NULL,
    seq          INTEGER NOT NULL,     -- statement number in the file (1-based, the engine's)
    term         VARCHAR NOT NULL,     -- the term's writeq text, e.g. data(ds(sales,sales_data)); avg 52 bytes on big_1000
    functor      VARCHAR NOT NULL,     -- [new] first functor, so "which rule fired" is a WHERE, not a parse of term
    l0 INTEGER NOT NULL, l1 INTEGER NOT NULL,   -- trace: lines
    b0 INTEGER NOT NULL, b1 INTEGER NOT NULL,   -- trace: byte offsets (strawman dropped them; Prolog needs them)
    roundtrip_ok BOOLEAN NOT NULL,     -- [new] L1 per statement: print → refold → same term?
    PRIMARY KEY (fileid, seq)
);

-- ------------------------------------------------------------- table_refs
-- every table occurrence in every block, with its role. Replaces `mentions`, `tables` and the
-- occurrence ids b_1:t_3 of [8000]. It is what neighborhood, blocklinks, search and story read.
CREATE TABLE IF NOT EXISTS table_refs (
    fileid     VARCHAR NOT NULL,
    block_id   VARCHAR NOT NULL,
    ref_no     INTEGER NOT NULL,       -- [8000 lineage.*_ref_id] t_1, t_2 … inside the block; the ref id is block_id || ':t_' || ref_no
    table_name VARCHAR NOT NULL,       -- [8000 lineage.*_canonical_name] lowercased lib.name; ds/1 becomes work.name
    lib        VARCHAR NOT NULL,       -- [8000 lineage.*_db_schema] the part before the dot
    role       VARCHAR NOT NULL,       -- read | write
    PRIMARY KEY (fileid, block_id, ref_no)
);

-- ------------------------------------------------------------------ edges
-- block-level facts only. File and project levels are the views below.
CREATE TABLE IF NOT EXISTS edges (
    fileid    VARCHAR NOT NULL,
    block_id  VARCHAR NOT NULL,        -- [8000 lineage.block_id] the block where the flow lands. Strawman: always ''
    src_table VARCHAR NOT NULL,        -- [8000 source_canonical_name]
    dst_table VARCHAR NOT NULL,        -- [8000 target_canonical_name]
    kind      VARCHAR NOT NULL,        -- ds | ctl  (ds_lineage vs ctl_lineage — a join key or WHERE column controls, it does not flow)
    freshness VARCHAR NOT NULL DEFAULT 'green',  -- [8000 lineage.freshness] green | yellow | red, computed at convert against the rows being replaced
    PRIMARY KEY (fileid, block_id, src_table, dst_table, kind)
);

-- the two inferred levels, derived. `file_edges` is a view; `project_edges` is a table refilled
-- at the end of every convert(folder) because neighborhood is the hottest question.
CREATE OR REPLACE VIEW file_edges AS
    SELECT w.fileid, w.block_id AS src_block, r.block_id AS dst_block, w.table_name
    FROM table_refs w JOIN table_refs r
      ON r.fileid = w.fileid AND r.table_name = w.table_name
    JOIN blocks bw ON bw.fileid = w.fileid AND bw.block_id = w.block_id
    JOIN blocks br ON br.fileid = r.fileid AND br.block_id = r.block_id
    WHERE w.role = 'write' AND r.role = 'read' AND br.n > bw.n;

CREATE TABLE IF NOT EXISTS project_edges (
    src_file   VARCHAR NOT NULL,       -- writer
    dst_file   VARCHAR NOT NULL,       -- reader
    table_name VARCHAR NOT NULL,
    PRIMARY KEY (src_file, dst_file, table_name)
);
-- refill: INSERT INTO project_edges SELECT DISTINCT w.fileid, r.fileid, w.table_name
--         FROM table_refs w JOIN table_refs r USING (table_name)
--         WHERE w.role = 'write' AND r.role = 'read' AND w.fileid <> r.fileid;

-- ---------------------------------------------------------------- librefs
CREATE TABLE IF NOT EXISTS librefs (
    fileid VARCHAR NOT NULL, lib VARCHAR NOT NULL,
    path   VARCHAR NOT NULL,           -- [8000 lineage.source_lib_path] from libname(lib, lit(path)); one row, not one column per edge
    PRIMARY KEY (fileid, lib)
);

-- ------------------------------------------------------------ human_edits
-- copied whole from [8000 human_edits]; one change: block_hash instead of block_id (§1.2)
CREATE TABLE IF NOT EXISTS human_edits (
    edit_id        VARCHAR PRIMARY KEY,
    edited_at      TIMESTAMP NOT NULL,
    editor         VARCHAR NOT NULL,
    action         VARCHAR NOT NULL,   -- add | confirm | correct | reject
    src            VARCHAR NOT NULL,   -- table (block/file level) or fileid (project level)
    dst            VARCHAR NOT NULL,
    table_name     VARCHAR NOT NULL,
    level          VARCHAR NOT NULL,   -- block | file | project
    comment        VARCHAR,
    fileid         VARCHAR,            -- NULL for project-level edits
    block_hash     VARCHAR,            -- the pin; NULL for file/project-level edits
    requires_check BOOLEAN NOT NULL DEFAULT FALSE,
    dismissed      BOOLEAN NOT NULL DEFAULT FALSE,
    freshness      VARCHAR NOT NULL DEFAULT 'green'
);

-- --------------------------------------------------------------- receipts   (L1 lives here)
CREATE TABLE IF NOT EXISTS receipts (
    fileid         VARCHAR PRIMARY KEY,
    statements     INTEGER NOT NULL,
    folded         INTEGER NOT NULL,
    roundtrip      INTEGER NOT NULL,   -- REAL: terms that print → refold to the same term (strawman counted folded terms)
    source_match   BOOLEAN NOT NULL,   -- REAL: rebuild_source(tokens, printed) == text (strawman: folded == statements)
    first_diff_seq INTEGER,            -- the narrowest failing statement, for UI3
    first_diff     VARCHAR,            -- "printed ⇢ refolded" of that statement
    rust_us        BIGINT NOT NULL,
    engine_version VARCHAR NOT NULL,
    rules_hash     VARCHAR NOT NULL
);

-- ---------------------------------------------------------- lineage_facts   (L4)
-- the four fact kinds of lineage.rs / lineage_common.pl, one row per fact, per side, per engine.
CREATE TABLE IF NOT EXISTS lineage_facts (
    fileid   VARCHAR NOT NULL,
    block_id VARCHAR,                  -- NULL when the engine could not attribute (Prolog prints none)
    side     VARCHAR NOT NULL,         -- sas | py         (lineage_left | lineage_right)
    engine   VARCHAR NOT NULL,         -- rust | prolog
    kind     VARCHAR NOT NULL,         -- schema | ds_lineage | col_lineage | ctl_lineage
    out_t    VARCHAR NOT NULL,         -- OUT table
    out_c    VARCHAR,                  -- OUT column (col_lineage) or the schema's column list as text (schema)
    in_t     VARCHAR,                  -- IN table  (ds/col/ctl)
    in_c     VARCHAR                   -- IN column (col_lineage) or the controlling column (ctl_lineage)
);
CREATE OR REPLACE VIEW lineage_diff AS         -- rows on one side only, for the rust engine
    SELECT fileid, 'sas_only' AS which, kind, out_t, out_c, in_t, in_c FROM
      (SELECT fileid, kind, out_t, out_c, in_t, in_c FROM lineage_facts WHERE side='sas' AND engine='rust'
       EXCEPT
       SELECT fileid, kind, out_t, out_c, in_t, in_c FROM lineage_facts WHERE side='py'  AND engine='rust')
    UNION ALL
    SELECT fileid, 'py_only', kind, out_t, out_c, in_t, in_c FROM
      (SELECT fileid, kind, out_t, out_c, in_t, in_c FROM lineage_facts WHERE side='py'  AND engine='rust'
       EXCEPT
       SELECT fileid, kind, out_t, out_c, in_t, in_c FROM lineage_facts WHERE side='sas' AND engine='rust');

-- -------------------------------------------------------------- testcases   (the rows L2 and L3 run on)
CREATE TABLE IF NOT EXISTS testcases (
    case_id    VARCHAR PRIMARY KEY,
    fileid     VARCHAR NOT NULL, block_id VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,       -- the input table these rows fill
    author     VARCHAR NOT NULL,       -- z3 | ai | human
    schema_    VARCHAR NOT NULL,       -- JSON, the *.schema.json of gen_block_testdata
    rows_      VARCHAR NOT NULL,       -- JSON array of rows (CSV text in the Bench)
    created_at TIMESTAMP NOT NULL
);

-- ------------------------------------------------------------------- runs   (L2 vs L3)
CREATE TABLE IF NOT EXISTS runs (
    run_id     VARCHAR PRIMARY KEY,
    fileid     VARCHAR NOT NULL, block_id VARCHAR NOT NULL,
    session    VARCHAR,                -- [bench run_block session_id]
    left_engine  VARCHAR NOT NULL,     -- prolog | rust   (output_left)
    right_engine VARCHAR NOT NULL,     -- spark           (output_right)
    left_ms    DOUBLE, right_ms DOUBLE,
    verdict    VARCHAR NOT NULL,       -- match | match-warn | differs | missing | no table | no inputs | no program  (bench_api.run_block)
    warn       VARCHAR,
    log        VARCHAR,
    at         TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS run_tables (          -- a block may write several tables; the Bench judges each
    run_id VARCHAR NOT NULL, table_name VARCHAR NOT NULL,
    verdict VARCHAR NOT NULL, n_mismatch INTEGER, left_rows INTEGER, right_rows INTEGER,
    PRIMARY KEY (run_id, table_name)
);
CREATE TABLE IF NOT EXISTS run_samples (         -- compare_rows' up-to-5 samples: the row, and how often each side has it
    run_id VARCHAR NOT NULL, table_name VARCHAR NOT NULL, sample_no INTEGER NOT NULL,
    row_ VARCHAR NOT NULL,             -- JSON array of cell strings
    left_count INTEGER NOT NULL, right_count INTEGER NOT NULL,
    PRIMARY KEY (run_id, table_name, sample_no)
);

-- ----------------------------------------------------------------- events
-- append-only. [8000 events] carried the whole bundle so replay could rebuild the db. Here a
-- convert is re-derivable from (file bytes, rules_hash), so convert events carry counts only;
-- human edits and runs are NOT re-derivable, so their events carry the full row as JSON.
CREATE SEQUENCE IF NOT EXISTS event_seq START 1;
CREATE TABLE IF NOT EXISTS events (
    seq     BIGINT PRIMARY KEY DEFAULT nextval('event_seq'),
    at      TIMESTAMP NOT NULL,
    session VARCHAR NOT NULL,
    kind    VARCHAR NOT NULL,          -- convert.ok | convert.error | edit | run | sweep …
    fileid  VARCHAR,
    payload VARCHAR                    -- JSON
);

-- ------------------------------------------------------------------- meta
CREATE TABLE IF NOT EXISTS meta (key VARCHAR PRIMARY KEY, value VARCHAR);   -- [8000 sync_meta] engine_version, rules_hash, folder, converted_at

-- ---------------------------------------------------------------- indexes  (see §3.1 for which ones earn their keep)
CREATE INDEX IF NOT EXISTS table_refs_by_table ON table_refs (table_name);
CREATE INDEX IF NOT EXISTS edges_by_dst        ON edges (dst_table);
CREATE INDEX IF NOT EXISTS edges_by_src        ON edges (src_table);
CREATE INDEX IF NOT EXISTS project_by_dst      ON project_edges (dst_file);
```

Three shape decisions, spelled out:

1. **node/4: one row per term, printed text plus a `functor` column.** One row per block (a
   blob of terms) would make "which statement failed round trip" and "which rule fired" a parse
   of text. One row per term with `roundtrip_ok` makes them a `WHERE`. The term text itself
   stays a string: DuckDB will not query inside a Prolog term anyway, and Prolog needs the
   exact `writeq` text back. 3303 rows, 173 KB — nothing.
2. **`blocks` holds all three texts on the row.** DuckDB is columnar: `file()` reads six narrow
   columns and never touches the 800 KB of text sitting in the same table (measured 1.7 ms).
   A separate `block_text` table would buy nothing and cost a join. `blocks(fileid, 0, 40)`
   reads 40 rows of text: 27 KB, 1 ms.
3. **`files.source` is stored.** The plan says "nothing returns a whole program", but UI1's
   code pane draws `FileDetail.code` — the whole file (see `node4_viz/src/api.ts`). It needs a
   separate question, `source(fileid)`, and one column. It is not returned by `file()`.

---

## 3. The ten questions → SQL

`⚠` marks the questions the plan's list gets wrong.

| # | plan §6 question | SQL (`?` = parameter) | index / why it is fast |
|---|---|---|---|
| 1 | `neighborhood(file\|table, up, down)` | seeds: `SELECT fileid FROM files WHERE fileid=?` or `SELECT DISTINCT fileid FROM table_refs WHERE table_name=?`. Then per hop, up: `SELECT src_file, table_name FROM project_edges WHERE dst_file IN (?…)`; down: `… WHERE src_file IN (?…)`. Cap at 200 files as `:8000` does. Nodes from `files`; run order (`score`, `cyclic`, `story`) computed in Rust over the returned edges — a port of `orderer.py`, not SQL. | `project_by_dst`, the PK on `src_file`; each hop is a keyed read of a few rows |
| 2 | `blocklinks(files)` | `SELECT w.fileid, w.block_id, w.block_id\|\|':t_'\|\|w.ref_no, r.fileid, r.block_id, r.block_id\|\|':t_'\|\|r.ref_no, w.table_name FROM table_refs w JOIN table_refs r USING (table_name) WHERE w.role='write' AND r.role='read' AND w.fileid<>r.fileid AND w.fileid IN (?…) AND r.fileid IN (?…)` | zonemap on `fileid` (rows land file by file) + `table_refs_by_table` |
| 3 | `file(fileid)` | `SELECT * FROM files WHERE fileid=?` minus `source`; `SELECT * FROM receipts WHERE fileid=?`; `SELECT block_id, n, kind, name, l0, l1, n_stmts, warn IS NOT NULL FROM blocks WHERE fileid=? ORDER BY n` | PK; measured 1.7 ms. **No text** — and note 85 KB for 1000 heads; UI2 may want `file()` to page heads too (OPEN) |
| 4 | `blocks(fileid, from, to)` | `SELECT block_id, n, kind, name, l0, l1, sas_text, py_pretty, warn FROM blocks WHERE fileid=? AND n>=? AND n<? ORDER BY n` | measured 1.05 ms; zonemaps make the `n` range a skip |
| 5 | `tablegraph(fileid)` | `SELECT DISTINCT table_name, lib FROM table_refs WHERE fileid=?` and `SELECT block_id, src_table, dst_table, kind, freshness FROM edges WHERE fileid=?`, then the human overlay (below) | zonemap on `fileid` |
| 6 | `story(table)` | `WITH RECURSIVE m AS (SELECT fileid, block_id, src_table, dst_table, 0 AS d FROM edges WHERE dst_table=? AND kind='ds' UNION ALL SELECT e.fileid, e.block_id, e.src_table, e.dst_table, d+1 FROM edges e JOIN m ON e.dst_table=m.src_table AND e.kind='ds' WHERE d<20) SELECT * FROM m ORDER BY d DESC` — the makers, furthest first | `edges_by_dst`; cycles are cut by `d<20` |
| 7 | `run(fileid, block_id, engine, session)` | a **write**: inputs from `testcases WHERE fileid=? AND block_id=?`, node/4 from `node4 WHERE fileid=? AND block_id=? ORDER BY seq`, program from `blocks.py_text`; writes `runs`, `run_tables`, `run_samples`, `events`. **UI3 only** (gold §7 C3) | PK on `node4 (fileid, seq)` + zonemap; the Spark job is the cost, not SQL |
| 8 | `convert(folder\|file)` | the write path, §3.2 | — |
| 9 | `proof(fileid)` ⚠ | **Dead in UI1/UI2** — gold §7 C2 removed the receipt bar and the background proof. In UI3 it becomes `verify(fileid)`: `SELECT * FROM v_verdicts WHERE fileid=?` (§5) | — |
| 10 | `search(q)` | `SELECT 'table' AS kind, table_name AS value, list(DISTINCT fileid ORDER BY fileid) AS files, count(DISTINCT fileid) AS n FROM table_refs WHERE table_name LIKE '%'\|\|?\|\|'%' GROUP BY table_name UNION ALL SELECT 'file', name, [fileid], 1 FROM files WHERE lower(name) LIKE … ORDER BY (value = ?) DESC, starts_with(value, ?) DESC, n DESC LIMIT 20` — the `:8000` ranking, in SQL, without the alias junk `mentions` had | measured 0.5 ms at 908 tables; at 100k distinct tables a `LIKE` scan is still a few ms. If not, add a `tables_index(table_name, n_files)` refilled with `project_edges` |

**Two questions the plan's list is missing**, both used by UI1 as ported (plan §7 keeps "the
edges drawer with level and provenance pills"; `node4_viz` calls `/api/edges` six times and
`POST /api/edits`):

| # | question | SQL |
|---|---|---|
| 11 | `edges(files, level, filter, offset, limit)` — the merged grid | the `_merged_edges` statement of `service.py`, over a `provided` CTE = `edges` rows as `level='block', provenance='fact'` ∪ `file_edges` as `'file','inferred'` ∪ `project_edges` as `'project','inferred'`, joined to `human_edits` **by `block_hash` through `blocks`** instead of by `block_id`. Copy the CTE; change only the join key. |
| 12 | `edit(action, …)` / `pending_edits()` | `add_edit` and `pending_checks` from `service.py`, verbatim, with `block_hash`. After every convert of a file: `flag_stale_edits` from `indexer.py`, with `block_hash IN (SELECT block_hash FROM blocks WHERE fileid=?)` as the "block still exists" test. |

**Flagged as not cheap:** nothing in 1–12 needs a full scan at 1000 blocks. At 30k files
(§3.1) question 6 is the only one whose cost depends on the data, not the query: a table with a
long backward story walks it all. `:8000` has the same shape and caps the neighbourhood at 200;
cap the story at 20 hops.

### 3.1 Which indexes earn their cost

DuckDB keeps a min/max **zonemap** per row group of 122,880 rows for every column, free. The
write path lands one file's rows together, so `fileid` is sorted on disk and any `WHERE
fileid=?` skips every row group but one — no index needed, at any corpus size. That is why the
strawman's `blocks_by_file`, `node4_by_block` and `edges_by_file` indexes are dropped: at 1000
blocks everything is in one row group anyway (measured 0.2 ms with or without them), and at 30k
files the zonemap does the same job for nothing.

ART indexes cost on every insert and are the one thing that makes bulk loads slow. Keep only
those on columns the queries hit **across** files, where zonemaps cannot help because the
values are scattered: `table_refs(table_name)`, `edges(src_table)`, `edges(dst_table)`,
`project_edges(dst_file)`. Plus the primary keys, which double as the idempotence guard. Add
nothing else until a measurement on 30 × `big_1000` says so.

### 3.2 The write path for `convert`

Measured today (strawman, prepared statements, one transaction per file): **562 ms** to store
1000 blocks + 3303 node/4 + 1204 edges + 908 `INSERT OR IGNORE` into `tables` + 7 ART/PK
index updates per row. Fold is 526 ms. Total 1089 ms of a 3000 ms budget.

The design adds rows: `table_refs` (~2.4k), `lineage_facts` (~5k for the SAS side; the PySpark
side too when L4 runs), `librefs`, `block_hash`, `functor`, and — the one real cost — the
**honest round trip**: print every term and refold it, as `main.rs` already does. That is a
second fold, about **+0.5 s**. So the estimate for the corrected convert is:

| step | today | corrected |
|---|---|---|
| fold + block ids + emit + pretty | 526 ms | 526 ms |
| print + refold (L1, real) | 0 (skipped) | ~500 ms |
| lineage per block (`lineage::sas::run` once per block, tagged) | ~doubled today: once per block for `name`, once more for the file | ~50 ms |
| store, prepared statements | 562 ms | ~700 ms (≈ 12k rows) |
| **total** | **1089 ms** | **~1.8 s**, inside 3 s |

Technique, in order of what to do first:

1. **One transaction per file.** `DELETE` the file's rows from every per-file table, insert
   the new rows, commit. A crash leaves every file either old or new, never half. DuckDB 1.5.5
   has no trouble deleting and re-inserting the same primary keys in one transaction (proven
   above; older DuckDB did). For a 30k-file folder that is 30k commits, each a small WAL
   append; the fold dominates by two orders of magnitude, so do not batch files per commit.
2. **Prepared statements are enough for the pass mark** — measured. Keep them for phase 1.
3. **Appender when it matters.** `Connection::appender("node4")` + `append_row` is DuckDB's
   bulk door: it batches into column vectors and skips the per-row planner. Expect the 562 ms
   to fall to ~100 ms (ASSUMED, not measured). Switch when a 30k-file convert is timed and the
   store share is visible, not before. The Appender works inside a transaction; use one per
   table per file.
4. **Never `INSERT OR IGNORE` row by row into a global table** (the strawman's `tables`, 908
   times per file, each a PK probe). `project_edges` is refilled once per `convert(folder)`
   with one `INSERT … SELECT`.
5. **Idempotence key = `(hash, rules_hash)`.** Skip a file only if both match the stored row.
   The strawman keyed on `hash` alone, so editing `sas.json` never reconverts anything.
6. **Freshness at write time**, as `apply_bundle` does: read the file's old `edges` and
   `blocks.block_hash` before the `DELETE` (same transaction), then colour each new edge green
   (its block_hash existed), yellow (block changed, flow existed), red (new flow). Then
   `flag_stale_edits(fileid)`.

---

## 4. What I rejected from the `:8000` schema, and why

| `:8000` thing | verdict | reason |
|---|---|---|
| `lineage.source_ref_id`, `target_ref_id` (`b_1:t_3`) | **kept as data, not as columns** | `node4_viz` draws occurrence nodes by these ids (`src_ref`/`dst_ref`, `blocklinks`). They are `block_id || ':t_' || ref_no` over `table_refs`; storing the string twice per edge is denormalisation for nothing |
| `source_db_schema`, `target_db_schema` | **rejected** | it is `split(name, '.')[0]`; `table_refs.lib` holds it once per occurrence |
| `source_lib_path`, `target_ref_path` | **moved** to `librefs(fileid, lib, path)` | a real fact from `libname(lib, lit(path))`, and it matters for migration (where `sales.` lives). One row per libref, not two columns on every edge |
| `dst_source_db_schema`, `dst_target_db_schema` | **rejected** | always empty; a destination schema map. When needed it is a `lib_map(lib, dst_schema)` table, never per-edge columns |
| `log_verified` | **rejected** | "always empty for now" in the exporter's own docstring. Its idea — "did something independent confirm this edge?" — is exactly L4, which is a table (`lineage_facts`), not a column |
| `edge_type` + the `level` view | **replaced** | store facts; derive the two inferred levels (§1.1). One row per fact means one place to be wrong |
| `folder_path` on `blocks` and `lineage` | **rejected** | its only reader is `COPY … PARTITION_BY`. That export is `COPY (SELECT b.*, f.folder FROM blocks b JOIN files f USING (fileid)) … PARTITION_BY (folder)` — a join once at export beats a column on 3.5M node/4 rows. `folder` stays on `files` |
| `mentions` | **replaced** by `table_refs` | a regex over `x.y` tokens that also catches SQL aliases (`a.cust_id` is one of the 87 "tables"). The parser knows the real occurrences and their roles; that is a better index and it is exact |
| the in-memory Aho-Corasick automaton | **rejected** | `search` over ~100k distinct names is a millisecond `LIKE`; measured 0.5 ms at 908 |
| `events.payload` = the whole bundle | **narrowed** | the bundle is re-derivable from bytes + rules; the payload is kept only for edits and runs, which are not |
| `sources` table | **folded** into `files.source` | same row, same key; DuckDB does not pay for a wide column it does not read |
| `sync_meta` | **kept** as `meta` | engine version and rules hash have to live somewhere the UI can show |
| `lost_flows` (ghost rows) | **deferred, OPEN** | real product logic for the edges drawer; needs the previous convert's edges, which the freshness step reads anyway. Add with the phase-2 drawer port |
| `macros`, `macro_calls` | **not created in phase 1** | the sas pack has **no** macro or `%include` rule (`grep macro sas.json` → nothing). Creating tables the engine cannot fill invites a fake receipt. When `sas_pack` learns `%macro`, copy both tables and the `<def_id>#<k>` instance-id scheme from `:8000` |
| `blocks.status` PARSED / PARTIAL / NOT_MATCHED | **rejected** | the Rust fold either folds a statement or not; `receipts.folded < statements` and `node4` rows say which. `files.status` keeps `converted | partial | error` because UI1's explorer colours by it |

---

## 5. The verification loop in the store (L1–L4)

Gold §3: a run passes when L1 round-trips exactly, `output_left == output_right`, and
`lineage_left == lineage_right`. Each must be answerable from rows.

| leg | stored where | the answer |
|---|---|---|
| **L1** round trip | `receipts.roundtrip`, `source_match`, `first_diff_seq`, `first_diff`; per statement `node4.roundtrip_ok` | `roundtrip = statements AND source_match`; the narrowest failing statement is `SELECT block_id, seq, term FROM node4 WHERE fileid=? AND NOT roundtrip_ok ORDER BY seq LIMIT 1` |
| **L2** `output_left` | `runs` with `left_engine = 'prolog'` (rust also allowed, for the engine-vs-engine check) | `left_rows`, `left_ms` per table in `run_tables` |
| **L3** `output_right` | same `runs` row, `right_engine = 'spark'` | `verdict`, `n_mismatch`, and the 5 samples in `run_samples` — the row-level diff UI3 shows |
| **L4** lineage | `lineage_facts` on both sides; `lineage_diff` view | the run passes when `SELECT count(*) FROM lineage_diff WHERE fileid=?` is 0 |

**The lineage diff that does not exist today.** exp_42 compared lineage by set-of-file-text
equality (`convert_api.py:198`: `len(set(L.values())) == 1`) — pass or fail, no *which*.
`lineage_facts` stores the four fact kinds of `lineage.rs` (`schema/2`, `ds_lineage/2`,
`col_lineage/4`, `ctl_lineage/3`) as columns, so `EXCEPT` gives the exact facts one side has and
the other lacks, per file, and — once the engine tags facts with their block — per block. The
engine change needed: `Facts` in `lineage.rs` carries the current block id when it records a
fact (today `Facts` has no block; the strawman gets a block's `name` by running the whole
lineage per block and string-splitting `ds_lineage(`). Prolog's output has no block id, so the
Prolog-vs-Rust comparison of L4 groups by everything except `block_id`.

**The roll-up UI3's corpus table reads**, one row per (file, block, leg), latest run wins:

```sql
CREATE OR REPLACE VIEW v_verdicts AS
SELECT r.fileid, NULL AS block_id, 'L1' AS leg,
       CASE WHEN r.roundtrip = r.statements AND r.source_match THEN 'pass' ELSE 'fail' END AS verdict,
       r.first_diff AS detail
FROM receipts r
UNION ALL
SELECT fileid, block_id, 'L2L3', verdict, log
FROM (SELECT *, row_number() OVER (PARTITION BY fileid, block_id ORDER BY at DESC) AS rn FROM runs) WHERE rn = 1
UNION ALL
SELECT f.fileid, NULL, 'L4',
       CASE WHEN count(d.fileid) = 0 THEN 'pass' ELSE 'fail' END,
       string_agg(d.which || ' ' || d.kind || '(' || d.out_t || ')', '; ')
FROM files f LEFT JOIN lineage_diff d USING (fileid) GROUP BY f.fileid;
```

The "three things on one screen" of gold §4 are then three keyed reads: the block (`blocks`),
the diff (`run_samples`), the rule (`node4.functor` of the block's terms).

`testcases` holds the rows the legs run on (Z3's today, the AI's later). Its shape is the gold
page's own OPEN question (rows only, or rows plus expectations); the table stores rows only,
and the expectation is whatever `output_left` computes.

---

## 6. Migration note — changes to `schema.rs` and `lib.rs`, in order

1. `files`: add `name`, `folder`, `rules_hash`, `source`; rename `hash` semantics to "file
   bytes only"; `status` values `converted | partial | error`.
2. `blocks`: add `block_hash` (FNV-1a over the block's statement texts, same hash function as
   the file), `n_stmts`; `warn` becomes `VARCHAR` (the emitter's warning line, from
   `bench_api.open_program`), NULL when none.
3. `node4`: add `functor`, `b0`, `b1`, `roundtrip_ok`; PK `(fileid, seq)`; drop the index.
4. `edges`: replace the six-column shape with the PK'd fact shape; **fill `block_id`** (today
   `''`); add `freshness`; drop `level` (a view now).
5. New tables: `table_refs`, `librefs`, `project_edges`, `human_edits`, `lineage_facts`,
   `testcases`, `run_tables`, `run_samples`, `meta`. New views: `file_edges`, `lineage_diff`,
   `v_verdicts`.
6. Drop `tables` and its `INSERT OR IGNORE` loop; `write_tables` goes.
7. `receipts`: drop `node4_same`, `pyspark_same`, `proof_state`, `prolog_ms` (gold C2: no
   background proof, no bar); add `first_diff_seq`, `first_diff`, `engine_version`,
   `rules_hash`. **Compute `roundtrip` and `source_match` for real** — copy the print → refold
   loop and `rebuild_source` from `main.rs` steps 3 and 3b into `fold_one`.
8. `runs`: add `run_id`, `session`, `left_engine`/`right_engine`, `left_ms`/`right_ms`,
   `warn`, `log`; drop `first_diff` (it is `run_samples`).
9. `events`: `seq` from a SEQUENCE, `session`, `payload` JSON; convert events carry
   `{hash, rules_hash, blocks, node4, edges}`.
10. `CLEAR_FILE`: add `table_refs`, `librefs`, `lineage_facts` (engine sides only — never
    `human_edits`, `runs`, `testcases`); refill `project_edges` at the end of `convert(folder)`.
11. `convert`: skip only when `hash` **and** `rules_hash` match; run `lineage::sas::run` once
    per block with the block tag (engine change in `lineage.rs`: `Facts` records the block);
    write `table_refs` from the same facts (`reads` → role read, the OUT table → role write,
    `ref_no` in first-seen order); compute freshness before the `DELETE`; call
    `flag_stale_edits` after the commit.
12. Readers: `file()` adds `n_stmts`, `warn`, the receipt fields, and never `source`; add
    `source(fileid)`, `tablegraph` with the human overlay, `story`, `blocklinks`,
    `neighborhood`, `edges`, `edit`, `pending_edits`; `search` as in §3 row 10.
13. `main.rs`: time `convert` with the real round trip and report fold / roundtrip / lineage /
    store separately, so the git note for phase 1 carries the four numbers of §3.2.

---

## Decisions

- **PROVEN ∎** — every number in §0 was measured on 2026-09-09 with the built strawman on
  `/private/tmp/bigcorpus/big_1000.sas` (copied to the scratchpad; db at
  `scratchpad/big.duckdb`). Bundled DuckDB `v1.5.5` read from `libduckdb-sys-1.10505.0/duckdb.tar.gz`.
- **PROVEN ∎** — the strawman's `roundtrip` never refolds and `source_match` is
  `folded == statements` (`lib.rs::fold_one`, and the receipt row `3303 / 3303 / 3303 / true`
  for a file `main.rs` would have checked for real). `edges.block_id` is `''` on all 1204 rows.
  A rules change never reconverts (skip keyed on `hash` alone).
- **PROVEN ∎** — `:8000`'s neighbourhood does not read `lineage`; project edges are computed
  per request (`service.py: neighborhood, _directed_reach, _materialize_provided`); only
  `BLOCK_FLOW` and `FILE_FLOW` are stored (41 + 1 rows); `human_edits` merges by the
  `_merged_edges` CTE; `requires_check` / `dismissed` / `freshness` as in §1.2
  (`indexer.flag_stale_edits`, `service.add_edit`).
- **PROVEN ∎** — the sas pack has no macro or `%include` rule (`raw/bench_stack/out/spec/sas.json`).
- **PROVEN ∎** — the plan's ten questions miss `edges(files, level)` and `edit(...)`, which
  `node4_viz/src/api.ts` calls; and `file()` cannot serve UI1's code pane without a whole-file
  `source`.
- **ASSUMED** — Appender cuts the 562 ms store to ~100 ms. Not measured; not needed for the
  pass mark.
- **ASSUMED** — the honest round trip costs about one more fold (~0.5 s). `main.rs` does it,
  but I did not time that step alone.
- **ASSUMED** — zonemaps alone keep per-file reads fast at 30k files because rows land
  file-by-file. True by DuckDB's storage design; not measured here.
- **ASSUMED** — Parquet export partitioned by folder is still wanted; it is not in any phase's
  pass mark.
- **OPEN** — `file()` for 1000 blocks is 85 KB. Fine for phase 1; UI2 may want heads paged
  like text. Waits on the phase-3 port.
- **OPEN** — `lost_flows` ghost rows: add with the phase-2 edges drawer, or not at all. Owner.
- **OPEN** — should `block_id` itself become `b_017_<hash8>` (as `:8000`) instead of a separate
  `block_hash`? That changes node/4 and therefore Prolog's view of blocks; the owner rule is
  "Prolog is the reference", so the Prolog side would have to change first. Left as a column.
- **OPEN** — `testcases` shape (rows only vs rows + expected) — the gold page's own open question.
- **OPEN** — L4 across engines: Prolog prints facts without block ids; either Prolog's
  `lineage_common.pl` learns to print the block, or L4 stays file-level for the Prolog side.
- **OPEN** — one DuckDB connection behind a lock (as `:8000`) or a connection per API thread.
  DuckDB allows one writer; the API can serialise writes and read from cloned connections.
