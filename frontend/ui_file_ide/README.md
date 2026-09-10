# frontend/ui_file_ide — UI2, the in-file window

**Why this folder exists.** UI2 is the window for **one file**: its SAS blocks beside the PySpark
they were converted into, the table graph that says which table feeds which, and a bottom strip for
output and log. It is the exp_42 Bench, extracted here on 2026-09-10 (Task 13) and repointed at the
Rust API so it reads the same store UI1 reads.

**Inputs → outputs.** `raw/bench_stack/server/bench.html` (the Bench page, copied verbatim then
transformed) + the Rust API on `:8110` → `bench.html`, served at `GET /bench`.

**Status (2026-09-10).** Running, and the phase-2 pass mark is met:
`23 blocks · 80 statements · folded 80/80 · round trip 80/80`, 46 cells, 12 table edges, no console
errors, with no Python process from this repo alive. Receipts and every difference from the
2026-09-09 baseline: `docs/plan/bronze/bronze_phase2_receipts.md`.

## What is in here

| path | what it is |
|---|---|
| `bench.html` | the window. One self-contained file — vanilla JS, no build step, no dependencies. `backend/api/src/routes/bench.rs` compiles it in with `include_str!` and serves it at `GET /bench`, so the release binary carries the window inside it. |
| `mockups/` | static design studies made before the port (see its own README). Not code that runs; `bench.html` sits **beside** them, not over them. |

## How to run it

```bash
backend/target/release/lineageq_store convert raw/bench_stack/out/spec/sas.json \
    corpus/team_finance backend/lineageq.duckdb
backend/target/release/lineageq_store convert raw/bench_stack/out/spec/sas.json \
    corpus/fixtures backend/lineageq.duckdb            # the exp_42 receipt file
backend/target/release/lineageq_api --db backend/lineageq.duckdb --port 8110
open http://localhost:8110/bench
```

Everything the page opens is a **fileid** — `sas/raw/09_customer_summary.sas`,
`test_vishnu_testdata_fixed.sas` — the same key `file()`, `blocks()`, `run()` and `source()` take.
It is not an on-disk path any more.

While editing the page, `LINEAGEQ_BENCH_HTML=frontend/ui_file_ide/bench.html` makes the server read
it from disk each request instead of serving the compiled-in copy, so a reload is enough.

## Where its answers come from

| the page asks | the API answers |
|---|---|
| open a file | `GET /api/file?fileid=` (receipts + block heads) then `GET /api/blocks?fileid=&from=0` (the SAS and PySpark text) then `GET /api/tablegraph?fileid=` (the table edges) |
| run one block | `POST /api/run {fileid, block_id, engine:"rust"}` |
| read a non-SAS file | `GET /api/source?fileid=` |
| the file tree, a folder page, similar files, a SAS listing, save a buffer | `GET /api/bench/{files,folder,similar,listing}`, `POST /api/bench/save` |

The Bench's single `/api/open` returned the whole file — 1.1 MB for a big one. Splitting it into
`file()` + `blocks()` is the point of the store: see `docs/plan/bronze/bronze_perf_receipts_exp42.md`.

## What is stubbed, and what was removed

- **Jupyter attach is gone** (Decision D17). The four Bench routes behind it (`sessions`,
  `session`, `exec`, `term`) are not implemented and not forwarded anywhere. With them went the
  session chips and the "paste a Jupyter link" box, the Console panel and its `p` rail button, and
  the gated terminal with its `run_all / fold / diff / compare` chips. The **Terminal** tab is
  still there and says one line: *Jupyter attach returns in M5.*
- **`/api/bench/similar` always answers `[]`** and says why: the score is a Jaccard over the
  Bench's Python signature index (`out/bench/sig`), which is not in the store.
- **`/api/bench/listing` always answers `{loaded:false}`** and says why: a pasted PROC PRINT is
  compared against the Bench's `out/pyspark_ravi` CSVs, which are not in the store. The paste box
  is gone with it.
- **A matching block shows no rows.** `POST /api/run` returns verdicts and, for a *differing*
  table, samples — not the data. The badge says `match`; the table under the cell is empty.
- **No Prolog, anywhere** (gold §5, §7 C6). The `prolog == rust` pill, the Rust ⇄ Prolog toggle,
  the receipt line and the help row that named both engines are stripped; `S.engine` is pinned to
  `"rust"`. `grep -ci prolog bench.html` returns 0, and `backend/api/tests/bench.rs` asserts it on
  the served bytes so it cannot quietly come back.
- **Cells are not windowed.** Every block is in the DOM, exactly as the Bench had it. That is
  Decision D2: extract as vanilla JS now, port to TypeScript with windowed cells in **M5**, whose
  pass marks (open to first cell < 1 s, ↓ key < 16 ms, DOM < 25 k elements on `big_1000.sas`) are
  unmeasured today.
- **Buffers save into the corpus.** `⌘S` writes `corpus/team_finance/sas/work/<stem>.py` through
  `POST /api/bench/save`, which refuses every path outside a `work/` stage. The Bench wrote a
  mangled copy under `out/bench/buffers/` instead.
