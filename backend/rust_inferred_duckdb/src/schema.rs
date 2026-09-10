//! The store's tables, exactly the eight named in the plan's section 5.
//!
//! **Why this exists.** The UIs must never wait for a fold. Everything the engine infers
//! about a folder is written here once, at convert time, so every later question is a
//! keyed read. `files`, `edges` and `events` keep the shapes the `:8000` store used;
//! `blocks`, `node4`, `receipts` and `runs` make the Bench's block model durable.
//!
//! **Inputs → outputs.** a DuckDB connection → the eight tables and their indexes.

/// Every table, created if absent. Safe to run on an existing store.
pub const DDL: &str = r#"
CREATE TABLE IF NOT EXISTS files (
    fileid        VARCHAR PRIMARY KEY,   -- path relative to the converted folder
    hash          VARCHAR,               -- content hash, so a reconvert can skip
    loc           INTEGER,
    status        VARCHAR,               -- ok | error
    error         VARCHAR,
    converted_at  TIMESTAMP,
    source        VARCHAR,               -- the file's full text, exactly as received
    crlf_normalised BOOLEAN              -- the bytes held CRLF; the engine was fed LF (D13)
);

CREATE TABLE IF NOT EXISTS blocks (
    fileid    VARCHAR,
    block_id  VARCHAR,
    n         INTEGER,                   -- 0-based order within the file
    kind      VARCHAR,                   -- DATA step | PROC SQL | PROC_PRINT | ...
    name      VARCHAR,                   -- the table it writes, when it writes one
    l0        INTEGER,
    l1        INTEGER,
    sas_text  VARCHAR,
    py_text   VARCHAR,
    py_pretty VARCHAR,
    warn      BOOLEAN,
    block_hash VARCHAR,                  -- hash_of(sas_text), so a run can tell if a block changed
    PRIMARY KEY (fileid, block_id)
);

CREATE TABLE IF NOT EXISTS node4 (
    fileid   VARCHAR,
    block_id VARCHAR,
    seq      INTEGER,
    term     VARCHAR,                    -- the node/4 term, printed
    trace_l0 INTEGER,
    trace_l1 INTEGER,
    trace_b0 INTEGER,                    -- byte offsets of the statement in the source
    trace_b1 INTEGER
);

CREATE TABLE IF NOT EXISTS edges (
    src_table VARCHAR,
    dst_table VARCHAR,
    kind      VARCHAR,                   -- ds | ctl
    fileid    VARCHAR,
    block_id  VARCHAR,
    level     VARCHAR                    -- block | file | project
);

CREATE TABLE IF NOT EXISTS tables (
    name                VARCHAR PRIMARY KEY,
    lib                 VARCHAR,
    first_writer_fileid VARCHAR
);

CREATE TABLE IF NOT EXISTS receipts (
    fileid       VARCHAR PRIMARY KEY,
    statements   INTEGER,
    folded       INTEGER,
    roundtrip    INTEGER,
    source_match BOOLEAN,
    node4_same   BOOLEAN,                -- filled by the Prolog proof, later
    pyspark_same BOOLEAN,
    proof_state  VARCHAR,                -- pending | same | differs
    rust_us      BIGINT,
    prolog_ms    BIGINT
);

CREATE TABLE IF NOT EXISTS runs (
    fileid     VARCHAR,
    block_id   VARCHAR,
    engine     VARCHAR,
    rows_n     BIGINT,
    ms         DOUBLE,
    match_     VARCHAR,                  -- match | match-warn | differs | missing
    first_diff VARCHAR,
    at_ts      TIMESTAMP
);

-- append-only, for replay; the idea is copied from file_dependencies_regex
CREATE TABLE IF NOT EXISTS events (
    at_ts  TIMESTAMP,
    kind   VARCHAR,
    fileid VARCHAR,
    detail VARCHAR
);

CREATE TABLE IF NOT EXISTS run_tables (
    fileid VARCHAR, block_id VARCHAR, engine VARCHAR, table_name VARCHAR,
    verdict VARCHAR,           -- match | match-warn | differs | missing
    n_mismatch BIGINT, missing_side VARCHAR, at_ts TIMESTAMP
);
CREATE TABLE IF NOT EXISTS run_samples (
    fileid VARCHAR, block_id VARCHAR, engine VARCHAR, table_name VARCHAR,
    n INTEGER,                 -- 0..4, at most five per table
    row_json VARCHAR, n_left BIGINT, n_right BIGINT
);
CREATE TABLE IF NOT EXISTS meta (key VARCHAR PRIMARY KEY, value VARCHAR);

-- What a human asserted about a flow, never mixed into the inferred tables above.
--
-- **Why this exists (Task 7, 2026-09-10).** `edges()` must answer the same merged view
-- `:8000` answers (`service.py::final_edges` over its `_merged_edges` CTE): the engine's
-- own rows with un-flagged customer edits applied — `reject` drops the matching block's
-- rows, `confirm` upgrades their provenance to `human_gold`, `add`/`correct` append a
-- `human_gold` row of their own. That merge needs a table of human assertions to merge
-- against, and this store had none. Columns are the fourteen `raw/lineage_server`'s own
-- `human_edits` carries (`server/indexer.py`), same names, same order, so a row can be
-- copied across without translation.
--
-- Additive only: nothing that converts a folder writes here. Rows arrive through
-- `insert_human_edit` (a UI action today, `edge_overrides` in M7).
CREATE TABLE IF NOT EXISTS human_edits (
    edit_id        VARCHAR PRIMARY KEY,
    edited_at      TIMESTAMP,
    editor         VARCHAR,
    action         VARCHAR,   -- add | confirm | correct | reject
    src            VARCHAR,
    dst            VARCHAR,
    table_name     VARCHAR,
    level          VARCHAR,   -- block | file | project
    comment        VARCHAR,
    block_id       VARCHAR,   -- pins a block-level edit; NULL for file/project level
    requires_check BOOLEAN,   -- the pinned block moved in a re-parse; ignored until re-confirmed
    fileid         VARCHAR,   -- a block id is only unique within a file
    dismissed      BOOLEAN,
    freshness      VARCHAR
);

CREATE INDEX IF NOT EXISTS blocks_by_file ON blocks (fileid, n);
CREATE INDEX IF NOT EXISTS node4_by_block ON node4  (fileid, block_id, seq);
CREATE INDEX IF NOT EXISTS edges_by_file  ON edges  (fileid);
CREATE INDEX IF NOT EXISTS edges_by_src   ON edges  (src_table);
CREATE INDEX IF NOT EXISTS edges_by_dst   ON edges  (dst_table);
"#;

/// Columns added after a store may already exist in the field. `CREATE TABLE IF NOT
/// EXISTS` above never alters a table that is already there, so every additive column
/// needs a statement here too, run once at `open()` and allowed to fail when the column
/// is already present.
///
/// **Why this exists (M4a, Decision D13).** `files.crlf_normalised` records that a file
/// arrived with CRLF line endings and was fed to the engine as LF. Stores converted
/// before M4a — `backend/lineageq.duckdb`, every `/tmp/*.duckdb` a receipt was taken
/// against — have a `files` table without it, and would otherwise fail their next insert.
pub const MIGRATIONS: &[&str] = &[
    "ALTER TABLE files ADD COLUMN crlf_normalised BOOLEAN",
];

/// Wipe one file's rows before rewriting them, so a reconvert is idempotent.
pub const CLEAR_FILE: &[&str] = &[
    "DELETE FROM blocks   WHERE fileid = ?",
    "DELETE FROM node4    WHERE fileid = ?",
    "DELETE FROM edges    WHERE fileid = ?",
    "DELETE FROM receipts WHERE fileid = ?",
    "DELETE FROM files    WHERE fileid = ?",
];
