#!/bin/zsh
# tools/build_stages.sh — regenerate auto_convert/ and, on first run only, seed work/
# and final_match/ for the three worked sample stems of the 2026-09-09 spec.
# Why: auto_convert is machine output and must be reproducible; work is the human's and
# must never be clobbered by a rerun.
set -eu
here="${0:A:h}/.."
tf="$here/corpus/team_finance/sas"
eng="$here/raw/bench_stack/rust_engine/target/release/lineageq_sas"
spec="$here/raw/bench_stack/out/spec/sas.json"
pre="$here/raw/bench_stack/codegen/sas_runtime_preamble.py"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
for stem in 09_customer_summary 15_join_risk_txn 18_dashboard_mart; do
  "$eng" "$spec" "$tf/raw/$stem.sas" "$tmp" "$pre" "$pre" >/dev/null
  cp "$tmp/${stem}_pretty_rust.py" "$tf/auto_convert/$stem.py"
  [[ -f "$tf/work/$stem.py" ]] || cp "$tf/auto_convert/$stem.py" "$tf/work/$stem.py"
  if [[ ! -f "$tf/final_match/$stem.py" ]]; then
    cp "$tf/work/$stem.py" "$tf/final_match/$stem.py"
    rows=$(grep -c . "$tf/raw/$stem.sas")
    cat > "$tf/final_match/$stem.verdict.json" <<EOJ
{
  "stem": "$stem",
  "accepted": false,
  "left_engine": "rust",
  "rows_compared": 0,
  "rows_matched": 0,
  "note": "seeded by tools/build_stages.sh; no DataMatch run yet (source lines: $rows)"
}
EOJ
  fi
  echo "staged $stem"
done
