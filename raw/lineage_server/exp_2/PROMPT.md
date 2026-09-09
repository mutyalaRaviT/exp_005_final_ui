# Experiment 2 — SAS Table-Lineage Extraction Using `parse` + Regex Wrappers + Scanner (Improved Prompt)

> **Changes from the original prompt** (`../prompt_using_regexs.md`):
>
> 1. **Normalization pinned down.** Canonical table names are `name.lower()` for matching
>    (`latest_writer` keys); display names keep the original source spelling.
> 2. **`parse` library usage clarified.** The `parse` library is case-sensitive and anchored, so:
>    statements are pre-split by the scanner, the leading keyword is matched case-insensitively
>    by a small helper, and `parse` captures only the structural remainder
>    (e.g. `"set {sources}"`). Never force `parse` to handle nesting.
> 3. **Comment handling made explicit.** `/* … */` comments are stripped before block splitting
>    (quote-aware). `* …;` statement comments are dropped at the statement level. Quoted
>    strings are honored by the scanner when finding semicolons and parentheses.
> 4. **Statement-level block splitting.** The scanner splits source into `;`-terminated
>    statements (quote- and paren-aware); a block runs from a `data` statement to its `run`
>    statement. This is stronger than a `data.*?run;` regex and reuses the scanner.
> 5. **Result statuses named.** `PARSED` / `NOT_MATCHED` / `PARTIAL` — a `PARTIAL` block
>    carries `unresolved` raw fragments instead of being silently dropped.
> 6. **Numbering restated unambiguously.** Within a block: reads first in source order, then
>    writes in source order (`t_1..`). (Opposite of exp_1; matches this spec's own examples.)
> 7. **Added `requirements.txt`** (parse, pytest) and kept `demo.py` as the runnable showcase.

## Goal

A Python prototype for **table-level** SAS lineage using: the `parse` library for structural
captures, small regex wrapper functions for lexical patterns, a tiny scanner for balanced
parentheses / quotes / comments / semicolon boundaries, and composable functions — no giant
regex, no full grammar, no guard framework.

## Lineage model

Node: `b_<block_id>:t_<table_no>_<table_name>`. Two edge types:

- **BLOCK_FLOW** (inside a block): every read → every write.
- **FILE_FLOW** (across blocks): latest earlier writer occurrence of a canonical name → each
  later reader occurrence. Separate pass; block parsers know nothing about other blocks.

## Pipeline

```
SAS source → strip comments → statement scanner → block splitter
          → statement parsers → TableOccurrence → BLOCK_FLOW → latest-writer → FILE_FLOW
```

## Data structures

`TableRef(name, raw)`, `TableOccurrence(id, name, block_id, table_no, role)`,
`Edge(source, target, edge_type)`,
`BlockResult(block_id, status, reads, writes, edges, unresolved)`.

## Layers (dependency hierarchy — no duplication)

```
IDENTIFIER → TABLE_NAME → TABLE_REF → TABLE_LIST → SET/MERGE/UPDATE/MODIFY → DATA_STEP → BLOCK_RESULT → FILE_GRAPH
```

1. **`regex_wrappers.py`** — lexical only: `identifier`, `table_name`
   (`[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?`), keyword matching. Never `.*` over nested structures.
2. **`scanner.py`** — `strip_comments`, `find_statement_end` (quote-aware `;`),
   `split_statements`, `balanced_parentheses` (returns span of a `( … )` region, handles
   nesting and quotes).
3. **`tables.py`** — `table_ref` = TABLE_NAME + optional opaque balanced dataset-options
   `( … )` (supports `keep=`, `where=(a in (1,2,3))`, `rename=(x=y)` without parsing them);
   `table_list` = one-or-more table_refs.
4. **`data_step.py`** — `parse_data_header`, `parse_set`, `parse_merge`, `parse_update`,
   `parse_modify`; all use the `parse` library for the capture and all delegate to
   `table_list`. Multiple targets in `data a b;` supported.
5. **`blocks.py`** — statement-driven block splitting, deterministic ids `b_1, b_2 …`.
6. **`graph.py`** — occurrence numbering (reads then writes), BLOCK_FLOW cross product,
   FILE_FLOW via `latest_writer: dict[str, TableOccurrence]`.

## Tests (pytest)

Core five: single set; two sources; two targets (`data work.x work.y;`); dataset options
(`keep=`); multi-line options with nested parens (`where=(a in (1,2,3))` + `rename=`).
Then MERGE with options (`by id;` ignored). Then the 3-block chain producing alternating
`BLOCK_FLOW / FILE_FLOW / BLOCK_FLOW / FILE_FLOW / BLOCK_FLOW`. Plus unit tests for every
primitive layer (regex wrappers, scanner, tables, data_step, block edges, file edges).

## Explicitly not implemented

SQL, column lineage, WHERE/KEEP/DROP/RENAME/BY semantics, FIRST./LAST., CALL EXECUTE, DOSUBL,
macros, macro variables, `%include`, PROC SQL. Dataset options are skipped structurally.

## Deliverables

Working implementation, `requirements.txt`, pytest suite, `demo.py` printing block structures
and all edges as `b_1:t_1_raw.customer -> b_1:t_2_work.customer`, with BLOCK_FLOW / FILE_FLOW
distinguished. Small and readable; the experiment tests whether **trusted regex/scanner
primitives + `parse` + composition** scale into a maintainable extractor an AI agent can extend
(e.g. add `PROC SORT` without touching existing primitives).
