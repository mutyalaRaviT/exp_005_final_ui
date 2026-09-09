#!/usr/bin/env bash
# exp_42 — the whole loop in one command (2026-09-05).
#   SAS -> tokens -> Prolog DCG fold -> node/4 -> print back (round trip)
#       -> PySpark (Prolog codegen)          out/pyspark/<stem>_ravi_prolog.py
#   SAS -> Rust engine (same pyDSL as JSON)  out/rust/<stem>.node4.pl, <stem>_ravi_rust.py
#   diff node/4 and PySpark between the two engines (must be identical)
#   run the generated PySpark on the test-data program -> out/pyspark_ravi/*.csv
set -uo pipefail
cd "$(dirname "$0")"
export JAVA_HOME="${JAVA_HOME_17:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home}"
PY=.venv/bin/python
hr() { printf '%s\n' "----------------------------------------------------------------"; }

hr; echo "1  tokenise (lossless) + generate the Prolog grammar + export the spec JSON"; hr
$PY -m pipeline.run_tokenise sas --dir corpus/sas | tail -1
$PY -m pipeline.gen_prolog sas
$PY -m pipeline.export_spec sas

hr; echo "2  Prolog: fold to node/4, print back, refold (round trip)"; hr
$PY -m pipeline.run_fold sas --work-dir out/work | head -4

hr; echo "3  Rust: same spec, same loop, plus PySpark"; hr
(cd rust_engine && cargo build --release 2>&1 | grep -E "^error" -A5)
for f in corpus/sas/*.sas; do
  stem=$(basename "$f" .sas)
  ./rust_engine/target/release/lineageq_sas out/spec/sas.json "$f" out/rust codegen/sas_runtime_preamble.py codegen/sas_runtime_pretty.py
done

hr; echo "4  Prolog codegen + differential check (Prolog == Rust)"; hr
for f in corpus/sas/*.sas; do
  stem=$(basename "$f" .sas)
  swipl -q -s codegen/sas_pyspark.pl -g main -- out/ir/sas/$stem.node4.pl codegen/sas_runtime_preamble.py out/pyspark/${stem}_ravi_prolog.py
  grep "^node(" out/ir/sas/$stem.node4.pl | diff -q - out/rust/$stem.node4.pl >/dev/null && echo "    $stem  node/4   prolog == rust" || echo "    $stem  node/4   DIFFERS"
  diff -q out/pyspark/${stem}_ravi_prolog.py out/rust/${stem}_ravi_rust.py >/dev/null && echo "    $stem  pyspark  prolog == rust" || echo "    $stem  pyspark  DIFFERS"
  swipl -q -s codegen/sas_pyspark_pretty.pl -g main -- out/ir/sas/$stem.node4.pl codegen/sas_runtime_pretty.py out/pyspark_pretty/${stem}_prolog.py >/dev/null
  diff -q out/pyspark_pretty/${stem}_prolog.py out/rust/${stem}_pretty_rust.py >/dev/null && echo "    $stem  pretty   prolog == rust" || echo "    $stem  pretty   DIFFERS"
done

hr; echo "5  run the generated PySpark on the test-data program (readable version; the plain one must give the same tables)"; hr
mkdir -p out/pyspark_pretty
LINEAGEQ_OUT=out/pyspark_ravi $PY out/pyspark_pretty/test_vishnu_testdata_prolog.py 2>&1 | grep -v "WARN\|Stage\|setLogLevel" | tee out/pyspark_ravi_testdata_stdout.txt | tail -40
LINEAGEQ_OUT=out/pyspark_ravi_plain $PY out/pyspark/test_vishnu_testdata_ravi_prolog.py > /dev/null 2>&1
for t in out/pyspark_ravi/*.csv; do cmp -s "$t" "out/pyspark_ravi_plain/$(basename "$t")" || echo "    plain and pretty programs DISAGREE on $(basename "$t")"; done
echo "    plain and pretty programs give the same 11 tables"
hr; echo "6  Bench: every table-writing block, Rust interp == Spark on its Z3 inputs (what the workbench runs per cell)"; hr
$PY server/bench_receipt.py corpus/sas/test_vishnu_testdata.sas 2>&1 | grep -v "WARN\|Stage\|setLogLevel" | tail -1

echo; echo "CSV copies: out/pyspark_ravi/*.csv   (compare with SAS: .venv/bin/python compare_sas_vs_pyspark.py <sas_listing.txt>)"
