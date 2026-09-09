#!/bin/sh
# exp_42 2026-09-08 — time the three swipl calls inside run_fold, for one stem, in isolation
stem="$1"
w="out/api/$stem/work"
d=pipeline/prolog/driver.pl
g=out/grammar/sas.pl
echo "stem $stem: $(wc -l < $w/$stem.stmts_in.pl) statements"
for pass in "main $w/$stem.stmts_in.pl /tmp/t1.pl" "unfold $w/$stem.terms_out.pl /tmp/t2.pl" "main $w/$stem.stmts_in2.pl /tmp/t3.pl"; do
  set -- $pass
  s=$(date +%s.%N)
  swipl -q -s $d -g $1 -- $g $2 $3
  e=$(date +%s.%N)
  echo "$(echo "$e - $s" | bc)s  swipl -g $1 on $(basename $2)"
done
