# team_finance — one corpus, both UIs (design)

**Date.** 2026-09-09. **Branch.** phase-2. **Status.** Approved in chat; plan not yet written.

## Why

The two UIs show different data, because they have different backends and different
corpora. UI1 (`raw/node4_viz`) proxies `/api` to the FastAPI server on `:8000`, which reads
`raw/lineage_server/output/explorer.duckdb` built from `inputs/ankitha_1` (25 SAS files).
UI2 (the Bench) is served by `raw/bench_stack/server/convert_api.py` on `:8042`, which reads
`corpus/sas`, `corpus/parts` and `testdata`. Nothing links the two. The owner's ask
(2026-09-09): remove all of it and stand up one local corpus, `team_finance/{sas,hive}`,
staged `raw -> auto_convert -> work -> final_match`, that both UIs read.

## Scope

This spec covers **A + D** only:

- **A** — the `team_finance` corpus and its four-stage folder contract, for SAS and Hive.
- **D** — both UIs re-pointed at one backend door.

Explicitly **out of scope**, each its own later cycle:

- **B — Hive conversion.** Hive files are present and browsable here, but are not converted.
- **C — the remaining 9 Rust API routes.** Tasks 6-12 continue after this, on the new corpus.

The ordering constraint that forces A before C: every landed Rust route is tested against a
seeded 25-file `ankitha` corpus (`test_state()` in `backend/api/src/lib.rs`). Swapping the
corpus after landing more routes would invalidate those tests twice.

## Layout

All paths are relative to `exp_005_final_ui_v3/` unless they start with `raw/`.

```
corpus/team_finance/
  sas/
    raw/           25 .sas  (from raw/lineage_server/inputs/ankitha_1)
    auto_convert/  engine output; regenerated every run, never hand-edited
    work/          the human working copy, seeded from auto_convert, edited in the Bench
    final_match/   the accepted .py plus its .verdict.json
  hive/
    raw/           6 .hql   (from lineageQ_aug_experiments/exp_014_vertical_slice_hadoop/corpus/hive/small)
    auto_convert/  empty until phase B
    work/          empty until phase B
    final_match/   empty until phase B
corpus/perf/       big_100.sas, big_1000.sas, big_2000.sas
                   (moved from raw/bench_stack/corpus/sas/)
```

`corpus/team_finance/` is top-level, not under `raw/`: it is the product's data, not a
copied-in source. `corpus/perf/` is separate because those files are fixtures, not a corpus
anyone browses.

### Stage ownership

| stage | written by | hand-edited | regenerated |
|---|---|---|---|
| `raw/` | nobody (source as received) | no | no |
| `auto_convert/` | the engine | **never** | every run |
| `work/` | the human, in the Bench | yes | no — seeded once from `auto_convert` |
| `final_match/` | the pipeline, on acceptance | no | on acceptance |

`final_match/<stem>.verdict.json` carries the DataMatch result that justifies acceptance:
rows compared, rows matched, and which engine produced the left side.

## Samples

All 25 SAS files live in `raw/`, but only three are carried through the later stages:

| stem | why |
|---|---|
| `09_customer_summary` | join + group by; the simplest complete conversion |
| `15_join_risk_txn` | depends on two upstream files; exercises cross-file lineage |
| `18_dashboard_mart` | downstream mart; shows a deep chain |

This deviates from the owner's "2-3 samples" deliberately, and was approved in chat: UI1's
value is the dependency chain, and three files make a boring graph. UI2 shows one file at a
time, so three worked examples is enough. The corpus is rich for lineage and small for
conversion at the same time.

Hive contributes `h01_create_select`, `h02_where_case`, `h03_group_having`,
`h04_join_two_tables`, `h05_insert_union`, `h06_nested_subquery` — all six, since they are
small (420 lines total) and are the exact files `pipeline/specs/hive.py` was written
against.

## One backend door

Today: UI1 proxies `/api` to `:8000`; UI2 is served by `:8042`. After this change both talk
only to the Rust API on `:8110`, which already forwards unlanded routes to those two Python
servers as oracles (`--oracle-a`, `--oracle-b`).

- UI1: `VITE_PROXY=http://localhost:8110` in `raw/node4_viz/vite.config.ts`.
- UI2: the Rust API gains a route serving `bench.html`; the page's relative `/api/...` calls
  then land on `:8110` without the page itself changing.

The Python servers keep running as oracles. Nobody talks to them directly. This is the
strangler fig that `backend/api/src/lib.rs` already describes — this spec only moves the two
UIs behind it, and lands no new routes.

## What is deleted

`raw/bench_stack/corpus/sas/test_vishnu*.sas`, `raw/bench_stack/corpus/parts/`,
`raw/bench_stack/testdata/`, `raw/lineage_server/inputs/ankitha_1/`, and the prebuilt
`raw/lineage_server/output/explorer.duckdb` (rebuilt from `team_finance`).

`big_100.sas`, `big_1000.sas` and `big_2000.sas` are **moved to `corpus/perf/`, not
deleted**: `backend/api/src/lib.rs` names `big_2000.sas` as a fixture for route tasks 8-10,
so deleting them would block phase C. Approved in chat.

## Pass marks

1. `corpus/team_finance/{sas,hive}/{raw,auto_convert,work,final_match}` all exist; `sas/raw`
   holds 25 files, `hive/raw` holds 6.
2. 24 of the 25 SAS files round-trip through the Rust engine (`source==rebuilt yes`).
   `13_risk_flags.sas` is the known exception — see Defects.
3. The three sample stems have files in `auto_convert/`, `work/` and `final_match/`, and
   each `final_match/<stem>.verdict.json` parses.
4. The three landed Rust routes (`files`, `search`, `neighborhood`) pass against a
   `test_state()` re-seeded from `corpus/team_finance/sas/raw/`.
5. UI1 on `:5174` and UI2 on `:8110/bench` both render, and both name the same files.

## Defects found while designing, not fixed here

- **Numeric literal round-trip.** `13_risk_flags.sas` fails `source==rebuilt`: the source
  `0.40` prints back as `0.4`. One file of 25. An engine bug in the printer, not a corpus
  problem. Recorded, not fixed in this scope.
- **The Hive tokeniser has never been run.** `pipeline/specs/hive.py` exists and documents
  the six corpus files it was written against, but no `.hql` was ever copied into
  `raw/bench_stack/`, and `out/spec/` holds only `sas.json` and `pyspark.json`. Phase B has
  to build `out/spec/hive.json` and run that spec for the first time. Nothing in this spec
  runs it, so this spec cannot tell whether it works.

## Risks

- **The DuckDB store must be rebuilt.** The shipped `explorer.duckdb` was built from
  `ankitha_1` by a different project tree. If rebuilding from `team_finance` needs tooling
  that was not copied in, UI1's lineage goes dark until phase C's Rust converter fills the
  store. This is the first thing the plan must verify, before anything is deleted.
- **`bench.html` assumes its own server.** It is 1,300 lines of one HTML file written
  against `convert_api.py`'s exact routes. Serving it from `:8110` works only while the
  oracle forwarding is faithful. Any route the Rust API lands but answers differently breaks
  the Bench silently.
