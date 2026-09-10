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
for stem in 09_customer_summary 15_join_risk_txn 18_dashboard_mart; do
  for stage in auto_convert work final_match; do
    [[ -f "$root/sas/$stage/$stem.py" ]] || { echo "MISSING sas/$stage/$stem.py"; fail=1 }
  done
  v="$root/sas/final_match/$stem.verdict.json"
  [[ -f "$v" ]] || { echo "MISSING $v"; fail=1 }
  python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$v" 2>/dev/null || { echo "BAD JSON $v"; fail=1 }
done
# 2026-09-10 (M0.1): corpus/fixtures/ — files that pin a pass mark, beside corpus/perf/.
# Not a four-stage corpus: the exp_42 receipt file only, see corpus/fixtures/README.md.
fx="${0:A:h}/../corpus/fixtures"
[[ -d "$fx" ]] || { echo "MISSING fixtures/"; fail=1 }
[[ -f "$fx/test_vishnu_testdata_fixed.sas" ]] || { echo "MISSING fixtures/test_vishnu_testdata_fixed.sas"; fail=1 }
[[ -f "$fx/README.md" ]] || { echo "MISSING fixtures/README.md"; fail=1 }
n_fx=$(ls "$fx"/*.sas 2>/dev/null | wc -l | tr -d ' ')

(( fail )) && { echo "corpus check FAILED"; exit 1 }
echo "corpus check ok: 25 sas, 6 hql, 8 stage folders, $n_fx fixture sas"
