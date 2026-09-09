# loops/ — the four equivalence loops, Prolog first, Rust as the mirror

**Why this folder exists.** exp_42 proved the parse loop (SAS → node/4 → SAS, byte
for byte). The owner asked on 2026-09-07 for the other three loops the method
promises — lineage, block-level execution, file-level execution — and for every
new piece to exist twice: in Prolog, as the readable rule set, and in Rust, as
the copy that will be productionised. Every loop prints one receipt line and a
Prolog-vs-Rust byte diff plus wall clock.

**Inputs → outputs.** Inputs: `corpus/sas/*.sas`, the node/4 files the engines
already write, the generated PySpark. Outputs: `out/loops/**` (lineage facts,
PySpark node/4, block and part datasets, execution results, timings) and the
receipts printed by `loops/run_loops.sh`.

## The four loops

| # | Loop | Reference (Prolog) | Mirror (Rust) | Equal when |
|---|---|---|---|---|
| 1 | Parse: SAS → node/4 → SAS | `out/grammar/sas.pl` (DCG) | `rust_engine` parser | source rebuilt == source, node/4 identical |
| 2 | Lineage: SAS node/4 → column lineage == PySpark node/4 → column lineage | `codegen/sas_lineage.pl`, `codegen/pyspark_lineage.pl`; PySpark parsed by `out/grammar/pyspark.pl` from `pipeline/specs/pyspark.py` | `lineage.rs`, `py_lineage.rs`; same spec as `out/spec/pyspark.json` | four lineage files identical (sas/prolog, sas/rust, py/prolog, py/rust) |
| 3 | Block-level execution | `codegen/sas_interp.pl` runs one block of node/4 on generated CSV inputs | `interp.rs` | per block, per output table: Prolog interp == Rust interp == Spark (the block's own PySpark program) |
| 4 | File-level execution, 4 quarters + full | same interpreter over the whole program | same | per part, per table: three executors agree; quarter aggregates add up to the full file |

The SAS side of loops 3 and 4 cannot run here (no SAS). The executable node/4
(exp_009's idea: an interpreter that proves the parse by the answers it
produces) stands in for SAS, and the block and part programs are also written
as `.sas` files for the owner to run on SAS OnDemand; `compare_sas_vs_pyspark.py`
diffs that listing when it arrives.

## Vocabulary

Column lineage facts, sorted, one per line, the same shape from every source:

    schema(Ds, [Col, ...]).            % columns of a dataset, in order
    ds_lineage(OutDs, InDs).           % OutDs reads InDs
    col_lineage(OutDs, OutCol, InDs, InCol).   % OutCol's value depends on InCol
    ctl_lineage(OutDs, InDs, InCol).   % InCol decides which rows reach OutDs (IF / WHERE / BY)

Names are lower-cased (SAS is case-insensitive); datasets are `lib.name`.

PySpark is parsed by the SAME pyDSL step as SAS: `pipeline/specs/pyspark.py`
is data, `gen_prolog.py` makes its DCG, `export_spec.py` its JSON. The one
engine addition (both tokenisers, marked `exp_42 2026-09-07`) is the spec key
`bracket_pairs`: a newline is an end of statement only outside brackets,
Python's own line-joining rule.

## Decisions

- **Prolog is the reference.** A rule is written once as a clause; the Rust
  function that mirrors it names the clause in a comment. Outputs are diffed.
- **Block isolation.** A block runs on freshly generated inputs (Z3 legs of
  its own conditions plus boundary and random rows), never on upstream output,
  so a wrong block cannot hide behind a right one.
- **Numbers print one way.** Integers without a decimal point, floats with 12
  significant digits, dates by their SAS format or as a day count from
  1960-01-01, missing as `.` — the convention `sas_print` already uses.

## Results (2026-09-07, `./loops/run_loops.sh`; full receipts in `out/loops/run_loops_receipts.txt`)

| Loop | Receipt | test_vishnu | test_vishnu_testdata | test_vishnu_testdata_fixed |
|---|---|---|---|---|
| 1 parse | folded, round trip, source rebuilt byte for byte; node/4 and PySpark text Prolog == Rust | 47/47, yes, identical | 80/80, yes, identical | 80/80, yes, identical |
| 2 lineage | PySpark folded through its own pyDSL; node/4 Prolog == Rust; four lineage files identical (sas/prolog, sas/rust, py/prolog, py/rust) | 18/18, 46 facts | 18/18, 46 facts | 18/18, 44 facts |
| 3 block | 11 blocks each on its own Z3 inputs; Prolog interp == Rust interp == Spark, byte for byte | (same program) | 11/11 PASS bytes | 11/11 PASS bytes |
| 4 file | 4 quarters + full; 11 tables x 5 parts x 3 executors identical; SUM/MAX/MIN of quarters == full (5/5) | — | 55/55 PASS bytes, partition test ok | (same rows) |

Wall clock (ms, whole process; Prolog = swipl start + consult per call, Rust = one binary; Spark = one JVM per program):

| Loop | Prolog | Rust | Spark |
|---|---|---|---|
| 1 parse, 3 files (fold + codegen) | 2,493 | 264 | — |
| 2 lineage, 3 files | 45,027 (44,886 of it is the DCG folding PySpark: ~15 s per file) | 87 | — |
| 3 block, 22 blocks (interp + block programs) | 649 | 189 | ~15,000 per block program |
| 4 file, 5 parts (fold + codegen + interp) | 4,562 | 159 | ~15,000 per part |

Findings:
- **Rust's all-alternatives parser was exponential on a PySpark method chain** (6 s per file) until memoised by (level, position): now 10-20 ms. Prolog pays a different price on the same grammar (~15 s per file through the backtracking DCG; SAS folds in under a second). Rust as the mirror is 10-500x faster on every loop; the Prolog numbers include process start-up per call.
- Block isolation caught nothing in the rules but caught the harness once: `random.Random(hash(block))` gave Spark and the interpreters different rows (per-process hash salt). Seeds are integers now.
- The SAS listing is still awaited; the interpreters stand in for SAS. When it arrives: `compare_sas_vs_pyspark.py` on the parts, and the block inputs under `out/loops/blocks/<stem>/<block>/in/` can be pasted as DATALINES.
- **OPEN** missing values: the interpreters follow SAS (`.` sorts low, `month(.)` is missing, `missing <= 3` is TRUE), Spark drops a null comparison. The generated data has no missing values yet, so the loops do not exercise this divergence; adding one missing row per input is the next mutation.
- `loops/skills_assessment.md` (subagent, 2026-09-07) judged which engine parts deserve a bench-card skill; the result is `.claude/skills/exp42_two_engine_pydsl`.
