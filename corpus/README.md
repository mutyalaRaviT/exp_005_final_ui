# corpus/ — the one local corpus

**Why this folder exists.** Until 2026-09-09 the two UIs read two different corpora through
two different backends, so they showed different data. This is the single corpus both now
read, through the Rust API on :8110.

**Inputs → outputs.** `team_finance/<lang>/raw/` is the source as received; the store
(`lineageq_store convert <spec> corpus/team_finance <db>`) indexes it into DuckDB and the
API answers from there.

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
  `raw/lineage_server/`. 24 of 25 round-trip; `13_risk_flags.sas` does not — `0.40` prints
  back as `0.4`, an engine bug in the printer.
- `team_finance/hive/raw/` — 6 HiveQL files, from
  `lineageQ_aug_experiments/exp_014_vertical_slice_hadoop/corpus/hive/small`. **Present but
  not converted:** the Hive tokeniser spec (`raw/bench_stack/pipeline/specs/hive.py`) has
  never been executed and there is no `out/spec/hive.json`. That is phase B.
- `perf/` — `big_100.sas`, `big_1000.sas`, `big_2000.sas`. Fixtures, not a corpus:
  `backend/api/src/lib.rs` names `big_2000.sas` for route tasks 8-10.

## Checks

- `tools/check_corpus.sh` — the structure contract.
- `tools/build_stages.sh` — regenerate `auto_convert/`, seed `work/` and `final_match/`.
