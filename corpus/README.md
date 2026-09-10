# corpus/ — the one local corpus

**Why this folder exists.** Until 2026-09-09 the two UIs read two different corpora through
two different backends, so they showed different data. This is the single corpus both now
read — but through two different doors, not one. UI1 reads it through the Rust API on
:8110 (`GET /api/files`, `/search`, `/neighborhood` from the store; `/edges`, `/blocklinks`,
`/file` forwarded to oracle_a). The Bench (UI2) reads the same corpus through its own
Python server on :8042, not through :8110: `GET /bench` on :8110 is only a 302 redirect to
`{oracle_b}/bench`.

**Why not one door for both (Ruling 6, 2026-09-09).** UI1 and the Bench both define
`/api/files`, with different response shapes — one origin cannot answer both without
either landing the Bench's own routes in Rust (phase C) or renaming them under a prefix
(editing the Bench's 1,300-line `bench.html`, explicitly out of scope here). Unifying the
Bench's routes is phase C's job, not this track's; do not re-attempt "one door for both"
without doing one of those two things first.

**Inputs → outputs.** `team_finance/<lang>/raw/` is the source as received; the store
indexes it into DuckDB and the API answers from there. Concrete, copy-pasteable build
command, run from `exp_005_final_ui_v3/`:

```
backend/target/release/lineageq_store convert raw/bench_stack/out/spec/sas.json corpus/team_finance backend/lineageq.duckdb
```

Expected output on success: 25 files, 26 blocks, 126 node4, 41 edges. If those counts
differ, the corpus or the spec has drifted — do not proceed assuming the store is good.

The resulting `backend/lineageq.duckdb` is build output, not source — it is generated from
`corpus/team_finance/` and the spec every time, and is gitignored (`backend/*.duckdb`).

## Stages

| stage | written by | hand-edited | regenerated |
|---|---|---|---|
| `raw/` | nobody — source as received | no | no |
| `auto_convert/` | `tools/build_stages.sh` | never | every run |
| `work/` | you, in the Bench | yes | no — seeded once from auto_convert |
| `final_match/` | the pipeline on acceptance | no | on acceptance |

`final_match/<stem>.verdict.json` carries the DataMatch result. Today every verdict says
`"accepted": false` with zeroed counts: no DataMatch has been run yet. Phase C fills them in.

## Contents

- `team_finance/sas/raw/` — 25 chained SAS files (customers, products, branches, accounts,
  transactions, FX, risk, compliance, dashboard). From
  `~/Desktop/sas2py_projects/file_dependencies_regex/inputs/ankitha_1`, via
  `raw/lineage_server/`. **25 of 25 round-trip** (M3a, 2026-09-10). They were 24 of 25 until
  then: `13_risk_flags.sas` printed `0.40` back as `0.4`, because a NUMBER token folded to a
  bare Prolog number and the lexeme was gone. The SAS `number` expr leaf now keeps it —
  `lit(Value, Lexeme)` — and both engines print the lexeme.
- `team_finance/hive/raw/` — 6 HiveQL files, from
  `lineageQ_aug_experiments/exp_014_vertical_slice_hadoop/corpus/hive/small`. **Present but
  not converted:** the Hive tokeniser spec (`raw/bench_stack/pipeline/specs/hive.py`) has
  never been executed and there is no `out/spec/hive.json`. That is phase B.
- `perf/` — `big_100.sas`, `big_1000.sas`, `big_2000.sas`. Fixtures, not a corpus:
  `backend/api/src/lib.rs` names `big_2000.sas` for route tasks 8-10.
- `fixtures/` — `test_vishnu_testdata_fixed.sas`, the exp_42 receipt file (23 blocks, 80
  statements, folded 80/80, round trip 80/80, 12 table edges, 11 runnable blocks). Fixtures,
  not a corpus: it is what `diff_route.py --corpus exp42` and Tasks 9/10/12/13 assert
  against. Task 5 deleted the folders it used to live in; registered here on 2026-09-10 by
  M0.1. See `fixtures/README.md`.

## Line endings (Decision D13, M4a)

The 25 `team_finance/sas/raw/*.sas` files have **CRLF** line endings; the fixtures and the
`perf/` files have LF. Nothing here is ever rewritten to fix that — `raw/` is the bytes as
received, and that is the whole point of a `raw/` stage.

Instead `inferred_duckdb::convert` normalises `\r\n` to `\n` **on intake**, before
tokenising, and records the fact in `files.crlf_normalised`. `files.source` still holds the
bytes exactly as they arrived, so `GET /api/source` and UI1's code pane show the file as it
is on disk.

Why it matters: the Python tokeniser reads with universal newlines
(`raw/bench_stack/pipeline/run_tokenise.py`), so on a CRLF file Prolog's node/4 trace
offsets run one byte short per line while Rust's count the `\r`. Measured on these 25
files, Prolog vs Rust: node/4 `prolog == rust` **0/25 before, 25/25 after**; plain PySpark
**13/25 before, 21/25 after** (the four still differing are the pre-existing emitter panics
— `coalesce` in 07 and 21, `today` in 08, `orderby(...)` in 14 — not line endings).

## Checks

- `tools/check_corpus.sh` — the structure contract.
- `tools/build_stages.sh` — regenerate `auto_convert/`, seed `work/` and `final_match/`.
