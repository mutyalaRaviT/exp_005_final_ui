#!/bin/zsh
# tools/check_corpus.sh — the corpus contract of the 2026-09-09 team_finance spec.
# Why: the four-stage layout is load-bearing (the store's fileids come from it) and is
# easy to break by hand. Exits non-zero with the first thing that is wrong.
set -u
root="${0:A:h}/../corpus/team_finance"
fail=0
for lang in sas hive; do
  for stage in raw auto_convert work final_match; do
    [[ -d "$root/$lang/$stage" ]] || { echo "MISSING $lang/$stage"; fail=1 }
  done
done
n_sas=$(ls "$root/sas/raw"/*.sas 2>/dev/null | wc -l | tr -d ' ')
n_hql=$(ls "$root/hive/raw"/*.hql 2>/dev/null | wc -l | tr -d ' ')
[[ "$n_sas" == 25 ]] || { echo "sas/raw: expected 25 .sas, found $n_sas"; fail=1 }
[[ "$n_hql" == 6  ]] || { echo "hive/raw: expected 6 .hql, found $n_hql"; fail=1 }
(( fail )) && { echo "corpus check FAILED"; exit 1 }
echo "corpus check ok: 25 sas, 6 hql, 8 stage folders"
