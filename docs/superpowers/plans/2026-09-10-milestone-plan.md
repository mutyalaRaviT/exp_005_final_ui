# exp_005 Milestone Plan (from the 2026-09-10 status audit)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. One milestone is handed to one implementer at a time; the dispatcher examines, never builds.

**Goal:** Take exp_005 from "compiler that agrees with itself" to "two shipping windows over one Rust store, with the four-leg verification loop running in a third dev-only window", in an order where every milestone leaves a screenshot and a git note behind.

**Architecture:** Rust API on :8110 answers twelve questions from a DuckDB store; two Python oracles (:8000 UI1 backend, :8042 Bench) are forwarded to until each question lands, then deleted. UI1 (`raw/node4_viz`) and UI2 (`raw/bench_stack/server/bench.html`) are extracted into `frontend/` once their routes are in Rust. The verification loop (L1 round trip, L2 Prolog left, L3 Spark right, L4 lineage parity) is landed as `run()` plus a lineage-compare route, then wrapped by UI3 behind a build flag.

**Tech Stack:** Rust (axum, duckdb crate), TypeScript (React Flow, ELK, Vite, vitest), SWI-Prolog, Python 3.11 venv in `raw/bench_stack/.venv` (z3 5.1.0, pyspark 4.2.0), Java 17 at `/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home`.

**Spec:** `docs/plan/gold/gold_three_uis_and_verification_loop.md` (owner gold, wins on conflict), `docs/plan/gold/gold_draft_exp_005_plan.md` (shape, store, API table), `docs/plan/silver/silver_phase2_implementation_plan.md` (Tasks 1–14, briefs in `.superpowers/sdd/silver_phase2_implementation_plan/task-*-brief.md`), `exp_005_status_2026-09-10_v2.pdf` (the status report this plan audits).

## Global Constraints

- Prolog is the reference, Rust mirrors it: any grammar or codegen change goes spec (`raw/bench_stack/pipeline/specs/sas.py`) → generated DCG → hand-written Prolog codegen mirrors → Rust, one commit each (Ruling, Task 5d).
- Regression net after any engine-touching task (Ruling D12): `80/80/80 yes` on `test_vishnu_testdata_fixed.sas` (23 blocks), `3303/3303/3303 yes` on `big_1000.sas`, `cargo test --workspace` green, and `run_all.sh`'s differential step.
- A route "lands" only when `oracle::forward` is deleted for it and `tools/diff_route.py <question>` runs clean or its accepted divergences are rows in `docs/plan/bronze/bronze_phase2_route_ledger.md`. No silent waivers.
- A pass-mark test asserts the pass mark. Never edit the assertion to match the implementation (Ruling D13).
- Every task ends with: a commit whose body says what changed and why, a `git notes add` with the measured numbers, and where a UI is touched a PNG in `docs/plan/bronze/evidence_<date>/`.
- `raw/` is the copied-in source. Edit it only where a brief names the line; name the source path in the first commit of every extracted file.
- UI1 and UI2 never show the word Prolog (gold §5). Prolog lives in UI3 and the dev loop only.
- API port is **:8110** (commit bf9a618). Fileids are **`sas/raw/<name>.sas`** (Task 5). Anything that still says :8100 or `ankitha_1/` is stale.
- No new Python except what `rules/` and the test-data generator already carry.

---

## Part A — Audit of the status PDF against the code (2026-09-10)

The PDF (`exp_005_status_2026-09-10_v2.pdf`) is right in its headline: the compiler half is real and measured, the proof half and the product half are not started. These are the places where it is wrong, stale, or inconsistent with the plan that already exists.

| # | PDF says | Code says | Effect on this plan |
|---|---|---|---|
| A1 | Route chart: 3 landed, 4 forwarded, **5 absent** | `backend/api/src/lib.rs:83` installs a fallback (Ruling 5): every non-landed `/api/*` GET forwards to oracle_a. **Nothing is absent**; 9 are forwarded. `convert` and `run` are POST-shaped and have no oracle by design. | Chart is wrong; no plan change. |
| A2 | `file()`, `blocks()`, `tablegraph()` listed as not started | `rust_inferred_duckdb/src/lib.rs` already exports `file` (l.469), `blocks` (l.505), `tablegraph` (l.522). Only the HTTP handlers, tests and the oracle diff are missing. | Tasks 9 and 10 are smaller than the PDF implies. |
| A3 | "Test data + Z3 + run" lane: nothing in the backend | `rust_rules_converter` already has `block-programs` and `interp` subcommands (`main.rs:87-89`), i.e. the L2 executor on the Rust side exists. Z3 row generation is Python in `raw/bench_stack/loops/gen_block_testdata.py`. | Task 12 shells out to the generator; it does not port it. |
| A4 | "every `final_match/*.verdict.json` says accepted: false" | Only three exist (09, 15, 18), the worked samples from Task 2. | Wording only. |
| A5 | Next step 3: "wire the html1 mock to real data, in TypeScript" | Task 13 brief: extract `bench.html` **as vanilla JS**, repoint 13 fetches, strip the Prolog surface. The TypeScript port with windowed cells is phase 3. | Follow Task 13. TypeScript is M5, not M2. |
| A6 | Next step 4: "copy `gen_block_testdata.py` + Z3 into `backend/testdata_rules/engine`" | Task 12 brief shells out to `raw/bench_stack/loops/gen_block_testdata.py` from `spawn.rs`. `backend/testdata_rules/engine/` is a README. | **Decision D1** below. Default: shell out (Task 12 as written); copying is M9. |
| A7 | Phase-2 briefs 7–14 are "the current plan, unchanged" | They predate Task 5 and bf9a618: they say `:8100` (now :8110), `ankitha_1/<f>.sas` (now `sas/raw/<f>.sas`), `npm test → 127` (now 174), and Tasks 9/10/12/13 use `test_vishnu_testdata_fixed.sas` and `diff_route.py --corpus exp42`, whose corpus dirs (`raw/bench_stack/corpus/sas`, `testdata/`) **Task 5 deleted**. The file survives only as `backend/rust_inferred_duckdb/tests/fixtures/test_vishnu_testdata_fixed.sas`. | **M0 exists to fix this** before any brief is handed out. |
| A8 | Task 8 "extract UI1 and repoint vite :8000 → :8100" | `raw/node4_viz/vite.config.ts:11` already proxies to :8110 (Task 4). UI1 also gained the Bench frame (7dd8924), which Task 8's `npm test → 127` count predates. | Task 8 is: move + smoke + pass marks with Python dead. |
| A9 | `run()` left side | Task 12 brief defaults `engine: "rust"` for `output_left`; gold §5 says **Prolog computes `output_left`** so the loop is not Rust checking Rust. | **Decision D6.** Task 12's pass mark may run with `rust` for speed, but the UI3 sweep (M8) must use `prolog`. |
| A10 | "0.40 prints as 0.4" bites step 1 | It bites round trip (L1) and `13_risk_flags.sas` only; UI1 pass marks do not read printed SAS. | Moved to M3 prerequisites (engine fixes), not M1. |
| A11 | Rust test count 29 | 32 today (`cargo test --workspace --release`, 2026-09-10; the PDF counted one crate short). Vitest 174/174. | — |
| A12 | Website step "01 Scan" 15% | The 30k-file regex explorer is in `~/Desktop/sas2py_projects/file_dependencies_regex`, outside this repo; nothing here. | Scan stays outside exp_005 until the owner says otherwise. |

Everything else in the PDF's two scoreboards was re-checked and stands (macro handling: 0 hits in the engine; UNION ALL codegen first-branch only at `emit.rs:201-202`; CASE has no `px`/`pe` rule; Hive spec never executed, no `out/spec/hive.json`; `frontend/`, `rules/`, `build_bin/` are README-only).

---

## Part B — Milestones, dependencies, acceptance

```
M0 re-baseline ─► M1 UI1 free of Python ─► M2 file/blocks/tablegraph/story ─► M3 run() L2 vs L3 ─► M4 close phase 2
                                                                                   │
                                          M5 UI2 TypeScript, windowed ◄────────────┘ (needs blocks window from M2, stripped UI2 from M4)
                                          M6 L4 lineage compare + verdict writer ◄── M3
                                          M7 gaps UI (accepted facts carried) ◄── M6
                                          M8 UI3 behind a build flag ◄── M3, M6
                                          M9 second language (Hive) + Param/Transform flow ◄── M4; independent of M5–M8
```

| M | Name | Depends on | Acceptance (all must be re-measured in the milestone, none inherited) | Visible result |
|---|---|---|---|---|
| **M0** | Re-baseline the phase-2 briefs and fixtures | — | (a) `corpus/fixtures/test_vishnu_testdata_fixed.sas` exists and is documented in `corpus/README.md`; (b) `tools/diff_route.py --corpus exp42` resolves to that folder and `files`/`search`/`neighborhood` still run clean on `ankitha` (0 unexplained diffs, 25/25); (c) briefs 7–14 say :8110, `sas/raw/`, 174 tests, and the fixture path; (d) `cargo test --workspace` green, `npx vitest run` 174/174; (e) a git note with the counts. | none; this is the day the plan stops lying |
| **M1** | UI1 without Python (Tasks 7 + 8) | M0 | Pass marks 1 and 2 with `:8000` and `:8042` **killed**: `11_branch_rollup` 6 files / 7 edges, `07_enrich_fx` 4 files / 3 edges, `18_dashboard_mart` edges drawer 25/25 with one `human_gold` row; `diff_route.py blocklinks` and `edges` clean; UI1 lives in `frontend/ui_across_file_ui/`, vitest 174/174 there; two PNGs in evidence. | UI1 draws from Rust alone; the top-bar pills for blocklinks and edges turn green |
| **M2** | The in-file questions (Tasks 9 + 10) | M0 (M1 not required; can run in parallel on a separate branch lane: `backend/api/src/routes/{file,blocks,tablegraph,story}.rs` only) | `file()` on the fixture: 23 blocks, receipts 80/80/80, no `sas` key; `blocks(0,40)` returns SAS + PySpark text; both **< 20 ms over HTTP** on `big_1000.sas` (3× curl); `tablegraph` on the fixture: 12 edges, `sales.q1_avg_sales` made by `b_007`; `story` makers in run order; ledger rows for any divergence. | `curl` receipts in the git note; no UI yet |
| **M3** | `run()`: L2 against L3 (Tasks 11 + 12) with engine prerequisites | M2 | Prereq commits (Prolog first, then Rust): 0.40 printer; UNION ALL PySpark all branches; CASE `px`/`pe` rules. Then `datamatch.rs` tests (normalisation, multiset, order) green; `POST /api/run` on `b_003` returns `match`; **pass mark 5: 11/11 blocks match** on the fixture; `runs`/`run_tables`/`run_samples` rows written; git note carries the 11 verdicts and both timings. | the `ran 0/23` pill becomes `ran 11/11 match` |
| **M4** | Close phase 2 (Tasks 13 + 14) | M1, M2, M3 | UI2 extracted to `frontend/ui_file_ide/bench.html`, 13 fetches repointed, `grep -ci prolog` = 0, header `23 blocks · 80 statements · folded 80/80 · round trip 80/80`; `oracle.rs` deleted; all seven pass marks re-measured in one sitting with no Python process alive; `bronze_phase2_receipts.md` written; ledger 12/12; gold §7 C1–C7 applied to `gold_draft_exp_005_plan.md` and `CLAUDE.md`; PR to main. | both windows run with one Rust binary; the release story is true for the first time |
| **M5** | UI2 in TypeScript, windowed | M4 | `big_1000.sas` open to first cell < 1 s; ↓ key < 16 ms; DOM < 25k elements; table graph collapses layers above 150 tables; screenshots vs the Bench baseline with every difference listed. Brief to be written from `frontend/ui_file_ide/mockups/README.md` and plan §7 after a design pass. | the html1 mock becomes real |
| **M6** | L4 lineage compare + the verdict writer | M3 | `GET /api/lineage_compare?fileid=` returns SAS facts vs PySpark facts (from `pyspark_lineage.pl` mirrored in Rust) with a diff; `final_match/<stem>.verdict.json` written by the pipeline with real counts and `accepted` decided by L2==L3 and L4 clean; a planted defect (negative control) flips a verdict to `false`. | the `verified` pill is computed, not painted |
| **M7** | Gaps UI: human-filled facts carried on unchanged blocks | M6 | An `edge_overrides`/`human_edits` row with `block_hash` survives a reconvert when the block text is unchanged and is dropped with a warning when it changed; one gap filled in UI2 shows as `HUMAN_GOLD` in UI1's edges drawer after reconvert. | first customer-shaped story |
| **M8** | UI3 skeleton behind a build flag | M3, M6 | A third window, excluded from the release build by a flag (**Decision D5**), sweeps a folder through L1–L4 with `engine: prolog` on the left (**D6**) and shows, for the first failing block: the block, the row diff, the rule id that fired. Release bundle contains no UI3 code (grep on the bundle). | the owner's bench |
| **M9** | Second language and flows | M4 | `pipeline/specs/hive.py` executed once → `out/spec/hive.json` + `out/grammar/hive.pl`; the 6 Hive files fold with counts recorded; then Param Flow and Transform Flow designs (macro/`%let` resolution is 0 lines today). Hive's latent ORDER BY bug fixed spec-first. | second language in the explorer tree |

**Lane rule for parallel implementers.** M1 owns `backend/api/src/routes/{blocklinks,edges,source}.rs`, `frontend/ui_across_file_ui/`, `tools/shot_ui1.mjs`. M2 owns `routes/{file,blocks,tablegraph,story}.rs`. Neither touches `rust_rules_converter`. M3 alone touches the engine and `pipeline/specs/sas.py`.

---

## Part C — Unresolved decisions (owner)

| ID | Question | Default this plan assumes until answered | Blocks |
|---|---|---|---|
| D1 | Does the Z3 test-data generator get ported into `backend/testdata_rules/engine`, or does `run()` shell out to `raw/bench_stack/loops/gen_block_testdata.py`? | Shell out (Task 12 as written); port later as part of M9 or when the Python venv becomes a shipping problem. | M3 |
| D2 | UI2: vanilla `bench.html` extraction now (Task 13) and TypeScript in M5, or skip straight to TypeScript? | Task 13 as written; M5 after. | M4 |
| D3 | Where does the exp42 fixture corpus live and is it visible to the Bench oracle (`SAS_DIRS`) for `diff_route --corpus exp42`? | `corpus/fixtures/`, appended to the Bench's `SAS_DIRS` so the oracle can answer; if the owner forbids editing `convert_api.py` again, M2/M3 use direct assertions (23/80/80/12/11) instead of the oracle for that corpus. | M0 |
| D4 | Is Spark the executor for `output_right`? (gold marks it ASSUMED) | Yes; `pyspark 4.2.0` in the venv, Java 17. | M3 |
| D5 | UI3 build flag: Cargo feature, Vite define, or both? | Both: a Cargo feature gates the routes UI3 needs, a Vite `define` gates the window; release script sets neither. | M8 |
| D6 | `output_left` engine: Rust `interp` (fast) or Prolog `sas_interp.pl` (independent)? | Task 12's pass mark may use `rust`; every UI3 sweep and every verdict in M6 uses `prolog`. Both must exist. | M3, M6, M8 |
| D7 | Is the across-files canvas SAS-only or does it also draw PySpark twins per block? (plan OPEN) | SAS-only through M4. | M5 |
| D8 | Corpus sweep scheduling for UI3 (owner rejected nightly) | Manual trigger only. | M8 |
| D9 | What is a "testcase" artefact: rows only, or rows plus expected values? | Rows only; expectation computed by the left engine. | M3 |

---

## Part D — M0 in full (the milestone dispatched first)

### Task M0.1: Register the fixture corpus

**Files:**
- Create: `corpus/fixtures/test_vishnu_testdata_fixed.sas` (byte copy of `backend/rust_inferred_duckdb/tests/fixtures/test_vishnu_testdata_fixed.sas`)
- Create: `corpus/fixtures/README.md`
- Modify: `corpus/README.md` (Contents section: add the `fixtures/` line)
- Modify: `tools/check_corpus.sh` (accept `fixtures/` beside `perf/`)
- Modify: `tools/diff_route.py:296-310` (`exp42_files()` reads `corpus/fixtures/`)
- Modify: `raw/bench_stack/server/convert_api.py` — the `SAS_DIRS` list Task 5 re-pointed: append `corpus/fixtures` (D3 default)

**Interfaces:**
- Produces: fileid `fixtures/test_vishnu_testdata_fixed.sas` for the Rust store when `convert` is pointed at `corpus/`; bare `test_vishnu_testdata_fixed.sas` for the Bench oracle (it keys by stem). `diff_route.py --corpus exp42` yields `[(fileid, relpath)]` from `corpus/fixtures/*.sas`.

- [ ] **Step 1: Write the failing check**

```bash
# tools/tests/test_diff_route.py — add:
def test_exp42_corpus_reads_corpus_fixtures():
    from diff_route import exp42_files
    files = exp42_files()
    assert any(f[0].endswith("test_vishnu_testdata_fixed.sas") for f in files), files
```

- [ ] **Step 2: Run it, watch it fail**

Run: `cd tools && python3 -m pytest tests/test_diff_route.py -k exp42 -v`
Expected: FAIL (empty list; the old dirs are gone)

- [ ] **Step 3: Create the folder and the copy**

```bash
mkdir -p corpus/fixtures
cp backend/rust_inferred_duckdb/tests/fixtures/test_vishnu_testdata_fixed.sas corpus/fixtures/
cmp backend/rust_inferred_duckdb/tests/fixtures/test_vishnu_testdata_fixed.sas corpus/fixtures/test_vishnu_testdata_fixed.sas && echo identical
```

`corpus/fixtures/README.md`:

```markdown
# corpus/fixtures — files that pin a pass mark

**Why this folder exists.** `test_vishnu_testdata_fixed.sas` is the exp_42 receipt file: 23 blocks,
80 statements, folded 80/80, round trip 80/80, 12 table edges, 11 runnable blocks that match on
Spark. Tasks 9, 10, 12 and 13 assert those numbers. Task 5 (2026-09-09) deleted the folders it used
to live in; this is its home now. Like `perf/`, it is a fixture, not a corpus anyone browses.

**Inputs → outputs.** the file → `diff_route.py --corpus exp42`, `backend/api` tests, the Bench oracle on :8042.
```

- [ ] **Step 4: Point `exp42_files()` at it**

In `tools/diff_route.py`, replace the body of `exp42_files()` so it globs `REPO_ROOT / "corpus" / "fixtures"` and returns `(p.name, f"fixtures/{p.name}")` pairs; update the module docstring lines 39–41 to name `corpus/fixtures/`.

- [ ] **Step 5: Run the check, watch it pass; run the whole tools test file**

Run: `cd tools && python3 -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Bench oracle sees the file**

In `raw/bench_stack/server/convert_api.py`, find `SAS_DIRS` (Task 5 set it to `corpus/team_finance/sas/raw`) and append the absolute path of `corpus/fixtures`. Start it (`cd raw/bench_stack && .venv/bin/python server/convert_api.py`, port 8042) and check:

```bash
curl -s localhost:8042/api/files | python3 -c "import json,sys; print([f for f in json.load(sys.stdin) if 'vishnu' in json.dumps(f)][:1])"
```
Expected: one entry. Stop the server afterwards only if you started it; if :8042 was already up when you began (owner's instance), do not kill it — say so in the return.

- [ ] **Step 7: `check_corpus.sh` and `corpus/README.md`**

Add `fixtures/` to the structure contract and to the Contents list (one line each). Run `tools/check_corpus.sh`; expected exit 0.

- [ ] **Step 8: Commit**

```bash
git add corpus/fixtures tools/diff_route.py tools/tests/test_diff_route.py tools/check_corpus.sh corpus/README.md raw/bench_stack/server/convert_api.py
git commit -m "M0.1: corpus/fixtures holds the exp_42 receipt file; diff_route exp42 corpus reads it

Task 5 deleted bench_stack/corpus/sas and testdata/, which diff_route.py's exp42
corpus and Tasks 9/10/12/13's fixtures pointed at. The file survived only as a
store test fixture. Copied byte-for-byte (cmp identical) to corpus/fixtures/,
registered in check_corpus.sh, corpus/README.md and the Bench oracle's SAS_DIRS."
```

### Task M0.2: Re-baseline briefs 7–14

**Files:**
- Modify: `.superpowers/sdd/silver_phase2_implementation_plan/task-{7,8,9,10,11,12,13,14}-brief.md`
- Modify: `docs/plan/silver/silver_phase2_implementation_plan.md` (same substitutions; it is the source the briefs were cut from)

- [ ] **Step 1: Find every stale token**

```bash
grep -nE ':8100|ankitha_1/|127 passed|bench_stack/corpus|bench_stack/testdata|--corpus exp42' \
  .superpowers/sdd/silver_phase2_implementation_plan/task-*-brief.md docs/plan/silver/silver_phase2_implementation_plan.md
```
Record the count in the return.

- [ ] **Step 2: Apply the substitutions**

| stale | current | why |
|---|---|---|
| `localhost:8100`, `:8100` | `:8110` | commit bf9a618 |
| `ankitha_1/<name>.sas` | `sas/raw/<name>.sas` | Task 5 rebuilt the oracle store with `sas/raw/` fileids |
| `npm test → 127 passed` | `npx vitest run → 174 passed` | 7dd8924 added 47 tests |
| `raw/bench_stack/corpus/…`, `raw/bench_stack/testdata/…` | `corpus/fixtures/…` | M0.1 |
| Task 8 "vite.config.ts:11 (:8000 → :8100)" | delete the item; note "already :8110 since Task 4" | fact |
| Task 8 "Create `frontend/ui_across_file_ui/` from `raw/node4_viz`" | keep, add "including `src/theme.css`, `TopBar`, `Rail`, `Drawer`, `BottomStrip`, `StatusBar` from 7dd8924" | UI1 grew a frame |

Do **not** change any pass-mark number (6/7, 4/3, 25/25, 23/80/80, 12 edges, 11/11, < 20 ms). If a number looks wrong, leave it and list it under deviations.

- [ ] **Step 3: Add the M0 note to each brief's head**

One line under the title: `> Re-baselined 2026-09-10 (M0): ports, fileids, fixture paths and test counts updated; pass marks unchanged.`

- [ ] **Step 4: Re-run the grep from Step 1**

Expected: 0 hits except inside the substitution table you may have quoted.

- [ ] **Step 5: Commit**

```bash
git add .superpowers/sdd/silver_phase2_implementation_plan docs/plan/silver/silver_phase2_implementation_plan.md
git commit -m "M0.2: re-baseline briefs 7-14 to :8110, sas/raw fileids, corpus/fixtures, 174 tests

The briefs predate Task 5 (corpus swap) and bf9a618 (port move). Pass marks untouched."
```

### Task M0.3: Prove the regression net still holds, and write the note

- [ ] **Step 1: Build and test**

```bash
cd backend && cargo build --release 2>&1 | tail -2 && cargo test --workspace --release 2>&1 | grep -E '^test result' 
cd ../raw/node4_viz && npx vitest run 2>&1 | grep -E 'Test Files|Tests '
```
Expected: every `test result: ok`, `Tests 174 passed`.

- [ ] **Step 2: Convert the corpus and check the counts**

```bash
cd /Users/mutyala/Desktop/lineageQ/lineageQ_sep_experiments/exp_005_final_ui_v3
rm -f /tmp/m0.duckdb && backend/target/release/lineageq_store convert raw/bench_stack/out/spec/sas.json corpus/team_finance /tmp/m0.duckdb
```
Expected (from `corpus/README.md`): 25 files, 26 blocks, 126 node4, 41 edges. If different, stop and report; do not proceed.

- [ ] **Step 3: Differential oracle on the three landed routes**

Start `:8000` only if it is not running (`lsof -ti:8000`); cwd must be `raw/lineage_server/server`, venv `raw/lineage_server/.venv`. Then:

```bash
for q in files search neighborhood; do python3 tools/diff_route.py $q --corpus ankitha; done
```
Expected: three "clean" lines, 0 unexplained diffs, 25/25.

- [ ] **Step 4: Fixture through the store**

```bash
rm -f /tmp/m0f.duckdb && backend/target/release/lineageq_store convert raw/bench_stack/out/spec/sas.json corpus/fixtures /tmp/m0f.duckdb
```
Expected: 1 file, 23 blocks, statements 80, folded 80. Record whatever it prints.

- [ ] **Step 5: Git note on the M0.2 commit and the wiki ledger line**

```bash
git notes add -m "M0 receipt 2026-09-10: cargo test <n> passed; vitest 174/174; team_finance 25/26/126/41; fixtures 1 file 23 blocks 80/80; diff_route files/search/neighborhood clean 25/25; stale tokens in briefs before/after: <a>/<b>" HEAD
```
Append to `docs/wiki_root.md` Ledger: `- 2026-09-10 — M0 re-baseline: briefs 7–14 corrected, corpus/fixtures/ registered. Plan: docs/superpowers/plans/2026-09-10-milestone-plan.md.` Commit that line.

**M0 acceptance = Part B row M0, all five items, numbers in the return.**

---

## Part E — What each later milestone reads

- M1: briefs `task-7-brief.md`, `task-8-brief.md` (after M0.2); `tools/shot_ui1.mjs`; `docs/plan/bronze/evidence_2026-09-09/`.
- M2: `task-9-brief.md`, `task-10-brief.md`; `rust_inferred_duckdb/src/lib.rs:469-530`.
- M3: `task-11-brief.md`, `task-12-brief.md`; `raw/bench_stack/pipeline/datamatch.py`, `server/datamatch.ts`, `loops/gen_block_testdata.py`, `codegen/sas_interp.pl`; the three engine-bug notes in `bronze_phase2_route_ledger.md` (Task 5d note) and `.superpowers/sdd/.../progress.md` (Unicode byte/codepoint).
- M4: `task-13-brief.md`, `task-14-brief.md`; gold §7 table C1–C7.
- M5–M9: no brief exists. Each starts with a brainstorm against the gold page and a written design under `docs/superpowers/specs/`, then a plan in this format.

## Self-review

- Spec coverage: gold §2 (three UIs) → M4, M5, M8; §3 four legs → L1 in place, L2/L3 M3, L4 M6; §4 UI3 → M8; §5 Prolog dev-only → M4 strip, D6; §7 C1–C7 → M4 Task 14 step 5. Plan §8 phases 1–6 → M1–M4 (phase 2), M5 (phase 3), M3+M6 (phases 4–5 as re-shaped by gold C2/C3), Tauri (phase 6) has **no milestone here**: it waits for M5 and is out of this plan's range; noted as a gap.
- Placeholders: none in Part D. Parts B rows M5–M9 deliberately say "brief to be written" because no design exists; that is a scheduling statement, not a placeholder in a task.
- Types: `exp42_files()` returns `list[tuple[str, str]]` in both M0.1 and diff_route's existing docstring; fileids match Task 5's `sas/raw/` form everywhere.

---

## Part F — M0 exam (2026-09-10) and the corrections it forces on this plan

M0 returned commits `a93e46c`, `243251f`, `6a00a8d`. Reproduced by the dispatcher: `diff_route.py files/search/neighborhood --corpus ankitha` clean at 1/1/25 calls, `cargo test --workspace --release` 32 passed 0 failed, `tools/check_corpus.sh` ok with 1 fixture, git note on HEAD verbatim as reported. **M0 accepted.**

Corrections to this plan from M0's deviations (each verified in the diff, not taken on trust):

| # | plan said | truth | fix |
|---|---|---|---|
| F1 | `SAS_DIRS` is in `convert_api.py` | it is `raw/bench_stack/server/bench_api.py:428` | Part D M0.1 file list is wrong; the edit landed in the right file |
| F2 | `exp42_files()` yields `fixtures/<name>.sas` | the Bench resolves paths against `raw/bench_stack/`; the working form is `../../corpus/fixtures/<name>.sas` (constant `BENCH_REL_FIXTURES`) | M2/M3 briefs use that form when they call the Bench oracle |
| F3 | Bench `/api/files` would list the fixture | `list_files()` has its own hard-coded dirs; it never will without a code change | do not write that check into any later brief |
| F4 | `ankitha_files()` was fine | it globbed the deleted `inputs/ankitha_1/` and returned `[]`, so the oracle check passed **vacuously** since Task 5 | fixed in M0.3; the 25/25 in M0's acceptance (b) is the first real one since the corpus swap |
| F5 | briefs get committed | `.superpowers/sdd/.gitignore` is `*`; briefs have never been tracked | **Decision D10** below |
| F6 | `python3 -m pytest` | bare python3 has no pytest; use `raw/lineage_server/.venv/bin/python -m pytest tools/tests/` from repo root | every later brief says so |
| F7 | 29 Rust tests | 32 | Part A row A11 corrected |
| F8 | :8042 is the Bench for this repo | pid on :8042 runs from `lineageQ_aug_experiments/exp_42_test_vishnu`; this repo's Bench must be started on a free port (M0 used :8342) | briefs that need oracle_b say "start your own on a free port; never kill :8042" |

| ID | Question | Default until answered | Blocks |
|---|---|---|---|
| D10 | Should `.superpowers/sdd/` briefs be version-controlled (change the `*` gitignore), or stay local working files? | Stay local; the silver plan in `docs/` is the tracked copy of the same text | nothing; hygiene |

Next dispatch: **M1** (Tasks 7 + 8), brief at `.superpowers/sdd/milestones/m1-brief.md`.

---

## Part G — M1 exam (2026-09-10)

M1 returned `d3e4b34` (Task 7) and `504bfd9` (Task 8). Reproduced by the dispatcher: `cargo test --workspace --release` 43 passed 0 failed; `diff_route.py blocklinks / edges / files / neighborhood --corpus ankitha` all clean (1/1/1/25 calls); with `:8000` stopped and its cwd verified, `tools/shot_ui1.mjs` printed `11_branch_rollup files=6 edges=7 edgeRows=23/23 humanGold=1`, `07_enrich_fx files=4 edges=3`, `18_dashboard_mart files=7 edges=6 edgeRows=25/25 humanGold=1`; `:8000` restarted through its venv afterwards. **M1 accepted.** Ledger grew by 164 accepted rows (blocklinks 80, edges 84), two root causes: B1 Rust block ids and refs differ from the Python scanner's naming, B2 one oracle-only `FILE_FLOW` self-row (`work.accounts_raw → work.accounts_raw`). Neither changes the canvas.

What M1 left behind, and who picks it up:

| # | finding | owner |
|---|---|---|
| G1 | `tools/tests/test_diff_route.py::test_load_accepted_on_the_real_ledger_seeded_by_this_task_is_empty` is **red**: it asserts the ledger has no accepted rows, which stopped being true the moment a route landed with divergences. Not a pass mark. | M2 (tools/tests in scope) |
| G2 | `source()` has no oracle check: `diff_route.py`'s `ROUTES["source"]` is still `no_oracle`. Shape chosen by M1: `GET /api/source?fileid= → {fileid, text, size}`. | M2 wires it to the Bench on a private port |
| G3 | No CLI writes `human_edits`; M1 seeded the dev store with a throwaway Python call. | M2 adds `lineageq_store human-edit <json>` (additive, `rust_inferred_duckdb/src/main.rs`) |
| G4 | Repo-root `node_modules` symlink (needed so `node tools/shot_ui1.mjs` resolves Playwright) and `frontend/ui_across_file_ui/tsconfig.tsbuildinfo` are not ignored. | M2 adds both to `.gitignore` |
| G5 | `tests/forward.rs` and `tests/health.rs` hard-code the landed set; every route task must bump them. | said in every later brief |
| G6 | TDD red is only provable with `:8000` stopped, because the fallback answers correctly. | said in every later brief |
| G7 | UI1 shows `could not load blocks for <fileid>` and a 502 on `/api/file/…` with Python dead. | M2's `file()`; M2 acceptance adds "shot_ui1 prints no CONSOLE ERRORS with :8000 stopped" |
| G8 | `raw/node4_viz` was copied, not moved; two 174-test suites exist. Deleting `raw/node4_viz` is a Task 14 (M4) decision. | M4; **Decision D11** |
| G9 | The one HUMAN_GOLD row still names `ankitha_1/…` fileids on both sides (it is what the stored edit says). | owner: re-key the edit to `sas/raw/` in M7 (gaps UI) or leave as history |

| ID | Question | Default until answered | Blocks |
|---|---|---|---|
| D11 | After M4, does `raw/node4_viz` get deleted (frontend/ is the source of record) or kept read-only as provenance? | Delete in Task 14, keep the README with the commit that named the source | M4 |

Next dispatch: **M2** (Tasks 9 + 10 plus G1–G4), brief at `.superpowers/sdd/milestones/m2-brief.md`.
