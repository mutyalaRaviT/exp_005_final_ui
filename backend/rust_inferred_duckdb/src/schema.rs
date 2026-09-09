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
    source        VARCHAR                -- the file's full text
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

CREATE INDEX IF NOT EXISTS blocks_by_file ON blocks (fileid, n);
CREATE INDEX IF NOT EXISTS node4_by_block ON node4  (fileid, block_id, seq);
CREATE INDEX IF NOT EXISTS edges_by_file  ON edges  (fileid);
CREATE INDEX IF NOT EXISTS edges_by_src   ON edges  (src_table);
CREATE INDEX IF NOT EXISTS edges_by_dst   ON edges  (dst_table);
"#;

/// Wipe one file's rows before rewriting them, so a reconvert is idempotent.
pub const CLEAR_FILE: &[&str] = &[
    "DELETE FROM blocks   WHERE fileid = ?",
    "DELETE FROM node4    WHERE fileid = ?",
    "DELETE FROM edges    WHERE fileid = ?",
    "DELETE FROM receipts WHERE fileid = ?",
    "DELETE FROM files    WHERE fileid = ?",
];
