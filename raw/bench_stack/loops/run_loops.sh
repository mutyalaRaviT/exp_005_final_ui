#!/usr/bin/env bash
# loops/run_loops.sh — the four loops, Prolog and Rust, with receipts and wall clock (exp_42, 2026-09-07).
#   ./loops/run_loops.sh            runs everything; Spark runs only where results are missing
#   ./loops/run_loops.sh --spark    also re-runs every Spark program (27 runs, ~7 minutes)
set -uo pipefail
cd "$(dirname "$0")/.."
export JAVA_HOME="${JAVA_HOME_17:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home}"
PY=.venv/bin/python; RS=./rust_engine/target/release/lineageq_sas
STEMS="test_vishnu_testdata test_vishnu_testdata_fixed"
FORCE_SPARK=${1:-}
mkdir -p out/loops; : > out/loops/timings.csv
hr() { printf '%s\n' "----------------------------------------------------------------"; }
now() { perl -MTime::HiRes=time -e 'printf "%d\n", time*1000'; }
# timed <loop> <engine> <item> <command...>: run, append the wall clock to timings.csv
timed() { local loop=$1 eng=$2 item=$3; shift 3; local t0=$(now); "$@"; local rc=$?; echo "$loop,$eng,$item,$(( $(now) - t0 ))" >> out/loops/timings.csv; return $rc; }
same() { diff -q "$1" "$2" >/dev/null && echo "    $3: identical" || { echo "    $3: DIFFERS"; diff "$1" "$2" | head -5; }; }

hr; echo "0  build + grammars"; hr
(cd rust_engine && cargo build --release 2>&1 | grep -E "^error" -A5)
$PY -m pipeline.gen_prolog sas >/dev/null; $PY -m pipeline.export_spec sas >/dev/null
$PY -m pipeline.gen_prolog pyspark >/dev/null; $PY -m pipeline.export_spec pyspark >/dev/null

hr; echo "1  LOOP 1 — parse: SAS -> node/4 -> SAS, both engines"; hr
$PY -m pipeline.run_tokenise sas --dir corpus/sas | tail -1
timed loop1_parse prolog corpus $PY -m pipeline.run_fold sas --work-dir out/work | grep -E "^test_vishnu|ALL"
for f in corpus/sas/*.sas; do s=$(basename $f .sas)
  timed loop1_parse rust $s $RS out/spec/sas.json $f out/rust codegen/sas_runtime_preamble.py codegen/sas_runtime_pretty.py | sed 's/^/    /'
  same <(grep "^node(" out/ir/sas/$s.node4.pl) out/rust/$s.node4.pl "$s node/4 prolog vs rust"
  timed loop1_parse prolog "$s codegen" swipl -q -s codegen/sas_pyspark.pl -g main -- out/ir/sas/$s.node4.pl codegen/sas_runtime_preamble.py out/pyspark/${s}_ravi_prolog.py >/dev/null
  same out/pyspark/${s}_ravi_prolog.py out/rust/${s}_ravi_rust.py "$s PySpark text prolog vs rust"
done

hr; echo "2  LOOP 2 — lineage: SAS node/4 -> facts == PySpark node/4 -> facts, both engines"; hr
$PY loops/extract_pyspark_body.py out/pyspark/*_ravi_prolog.py >/dev/null
$PY -m pipeline.run_tokenise pyspark --dir corpus/pyspark | tail -1
timed loop2_lineage prolog "pyspark fold" $PY -m pipeline.run_fold pyspark --work-dir out/work_py | grep -E "^test_vishnu" | sed 's/NO  *FAIL/strings print single-quoted (canonical); terms equal/'
mkdir -p out/loops/lineage
for s in test_vishnu $STEMS; do
  timed loop2_lineage rust "$s pyspark fold" $RS out/spec/pyspark.json corpus/pyspark/$s.py out/rust_py 2>/dev/null | sed 's/^/    /'
  same <(grep "^node(" out/ir/pyspark/$s.node4.pl) out/rust_py/$s.node4.pl "$s PySpark node/4 prolog vs rust"
  timed loop2_lineage prolog "$s sas" swipl -q -s codegen/sas_lineage.pl -g main -- out/ir/sas/$s.node4.pl out/loops/lineage/$s.sas.prolog.pl >/dev/null
  timed loop2_lineage prolog "$s py" swipl -q -s codegen/pyspark_lineage.pl -g main -- out/ir/pyspark/$s.node4.pl out/loops/lineage/$s.py.prolog.pl >/dev/null
  timed loop2_lineage rust "$s sas" $RS lineage out/spec/sas.json corpus/sas/$s.sas out/loops/lineage/$s.sas.rust.pl >/dev/null
  timed loop2_lineage rust "$s py" $RS lineage out/spec/pyspark.json corpus/pyspark/$s.py out/loops/lineage/$s.py.rust.pl >/dev/null
  n=$(wc -l < out/loops/lineage/$s.sas.prolog.pl | tr -d ' ')
  for v in sas.rust py.prolog py.rust; do same out/loops/lineage/$s.sas.prolog.pl out/loops/lineage/$s.$v.pl "$s lineage ($n facts) sas.prolog vs $v"; done
done

hr; echo "3  LOOP 3 — block level: every step on its own Z3 inputs; Prolog interp == Rust interp == Spark"; hr
for stem in $STEMS; do
  $PY loops/gen_block_testdata.py $stem | tail -1
  timed loop3_block prolog "$stem block programs" swipl -q -s codegen/pyspark_block.pl -g main -- out/grammar/pyspark.pl out/ir/pyspark/$stem.node4.pl codegen/sas_runtime_preamble.py out/loops/blocks/$stem >/dev/null
  timed loop3_block rust "$stem block programs" $RS block-programs out/spec/pyspark.json corpus/pyspark/$stem.py codegen/sas_runtime_preamble.py out/loops/blocks/$stem >/dev/null
  for d in out/loops/blocks/$stem/b_*/; do b=$(basename $d)
    timed loop3_block prolog "$stem $b" swipl -q -s codegen/sas_interp.pl -g main -- out/ir/sas/$stem.node4.pl $d/in $d/prolog $b > $d/prolog.log 2>&1
    timed loop3_block rust "$stem $b" $RS interp out/spec/sas.json corpus/sas/$stem.sas $d/in $d/rust $b > $d/rust.log 2>&1
    for p in $d/block_*_prolog.py; do
      same $p ${p%_prolog.py}_rust.py "$stem $b $(basename $p .py | sed 's/block_//;s/_prolog//') block program prolog vs rust"
      if [ -n "$FORCE_SPARK" ] || [ ! -d $d/spark ]; then timed loop3_block spark "$stem $b" env LINEAGEQ_OUT=$d/spark $PY $p > $d/spark.log 2>&1; fi
    done
  done
done

hr; echo "4  LOOP 4 — file level: four quarters + full; Prolog interp == Rust interp == Spark; quarters add up"; hr
$PY loops/gen_file_parts.py | tail -1
$PY -m pipeline.run_tokenise sas --dir corpus/parts | tail -1
mkdir -p out/tokens/parts out/ir/parts out/loops/parts/pyspark out/loops/parts/rust out/loops/parts/spark
for f in corpus/parts/*.sas; do s=$(basename $f .sas)
  timed loop4_file prolog "$s fold" $PY -m pipeline.run_fold sas --file $s --out-dir out/ir/parts --work-dir out/work_parts | grep -E "^test_vishnu" | sed 's/^/    /'
  mv out/tokens/sas/$s.tokens.json out/tokens/parts/
  timed loop4_file prolog "$s codegen" swipl -q -s codegen/sas_pyspark.pl -g main -- out/ir/parts/$s.node4.pl codegen/sas_runtime_preamble.py out/loops/parts/pyspark/${s}_prolog.py >/dev/null
  timed loop4_file rust "$s fold+codegen" $RS out/spec/sas.json $f out/loops/parts/rust codegen/sas_runtime_preamble.py >/dev/null 2>&1
  same out/loops/parts/pyspark/${s}_prolog.py out/loops/parts/rust/${s}_ravi_rust.py "$s PySpark text prolog vs rust"
  timed loop4_file prolog "$s interp" swipl -q -s codegen/sas_interp.pl -g main -- out/ir/parts/$s.node4.pl /nonexistent out/loops/parts/interp_prolog/$s >/dev/null
  timed loop4_file rust "$s interp" $RS interp out/spec/sas.json $f /nonexistent out/loops/parts/interp_rust/$s >/dev/null
  if [ -n "$FORCE_SPARK" ] || [ ! -d out/loops/parts/spark/$s ]; then timed loop4_file spark "$s" env LINEAGEQ_OUT=out/loops/parts/spark/$s $PY out/loops/parts/pyspark/${s}_prolog.py > out/loops/parts/spark/$s.log 2>&1; fi
done

hr; echo "5  receipts"; hr
$PY loops/report.py test_vishnu_testdata test_vishnu_testdata_fixed
echo; echo "SAS files for the owner to run on SAS OnDemand: corpus/parts/*.sas (loop 4); block inputs under out/loops/blocks/<stem>/<block>/in/"
