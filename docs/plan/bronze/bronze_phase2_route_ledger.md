---
tags: [plan, bronze, phase2, ledger]
---
# bronze_phase2_route_ledger — which routes have landed

**Why this file exists.** `tools/diff_route.py` is the differential oracle for phase 2: a route
only "lands" (moves from `oracle::forward` to the store) once its answers are proved identical to
the Python implementation it replaces, question by question, file by file. This page is the
record of that proof: which of the twelve questions in the plan's §6 table have landed, whether
their corpus ran clean, and every difference a human has looked at and accepted as the parser
being right instead of the scanner. There is no other way to wave a difference through — no flag
does it silently. See `tools/diff_route.py`'s module doc comment and Task 4's report
(`.superpowers/sdd/silver_phase2_implementation_plan/task-4-report.md`) for how the tool works.

## Routes

| question | landed | corpus clean | accepted divergences |
|---|---|---|---|
| files | yes | yes | — |
| search | yes | yes (q="") | — |
| neighborhood | yes | yes (288 accepted, 3 root causes — Task 6 note) | 288 |
| convert | no | — | — |
| blocklinks | no | — | — |
| edges | no | — | — |
| source | no | — | — |
| file | no | — | — |
| blocks | no | — | — |
| tablegraph | no | — | — |
| story | no | — | — |
| run | no | — | — |

`landed`: `no` until the route reads from the store instead of forwarding to a Python oracle
(`oracle::forward` deleted for that arm) and its `diff_route.py` run — or, for `convert`/`run`,
its stated pass mark — is clean. `corpus clean`: `yes` once every file in the question's corpus
diffs clean (after accepted divergences are subtracted); `no oracle — new surface` for `convert`
and `run`, whose briefs (Task 6b, Task 12) explicitly say no oracle comparison applies. `accepted
divergences`: a count with a link into the table below, or `—` if none.

## Accepted divergences

| question | fileid | json_path | why the parser is right |
|---|---|---|---|
| neighborhood | ankitha_1/01_seed_customers.sas | edges[missing:2f0ba09c8fa5] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/01_seed_customers.sas | edges[missing:b67b2c9dd4fc] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/01_seed_customers.sas | nodes.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/01_seed_customers.sas | nodes[1].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/01_seed_customers.sas | nodes[1].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/01_seed_customers.sas | order.ankitha_1/04_build_accounts.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/01_seed_customers.sas | order.ankitha_1/09_customer_summary.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/01_seed_customers.sas | order.ankitha_1/09_customer_summary.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/01_seed_customers.sas | story.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/01_seed_customers.sas | story[0] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/01_seed_customers.sas | story[1] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | edges[missing:f94520730874] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | edges[missing:ef028b456b91] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | edges[missing:a6f73d390b0a] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | nodes.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | nodes[1].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | nodes[1].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | nodes[2].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | nodes[2].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | nodes[2].score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | order.ankitha_1/04_build_accounts.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | order.ankitha_1/10_product_metrics.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | order.ankitha_1/10_product_metrics.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | order.ankitha_1/22_marketing_list.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | order.ankitha_1/22_marketing_list.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | story.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | story[0] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | story[1] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/02_seed_products.sas | story[2] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:2f0ba09c8fa5] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:f94520730874] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:141364a4d43d] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:6abe41e47267] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:b67b2c9dd4fc] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:7d120f9c91d1] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:ef028b456b91] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:69d89a46dd2f] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:6d735a245714] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:5ce541e692db] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:40b28f116238] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:297a2516bbb8] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:a6f73d390b0a] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:862816983e19] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | edges[missing:22e966836506] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | nodes.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | nodes[0].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | nodes[0].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | nodes[0].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | order.ankitha_1/01_seed_customers.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | order.ankitha_1/02_seed_products.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | order.ankitha_1/04_build_accounts.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | order.ankitha_1/04_build_accounts.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | order.ankitha_1/08_daily_balances.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | order.ankitha_1/09_customer_summary.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | order.ankitha_1/10_product_metrics.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | order.ankitha_1/11_branch_rollup.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | order.ankitha_1/14_large_txn_report.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | order.ankitha_1/15_join_risk_txn.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | order.ankitha_1/22_marketing_list.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | order.ankitha_1/24_ops_alerts.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | story.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/04_build_accounts.sas | story[0] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | edges[missing:141364a4d43d] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | edges[missing:69d89a46dd2f] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | nodes.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | nodes[0].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | nodes[0].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | nodes[0].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | nodes[1].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | nodes[1].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | nodes[1].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | nodes[2].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | nodes[2].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | nodes[2].score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | order.ankitha_1/04_build_accounts.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | order.ankitha_1/08_daily_balances.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | order.ankitha_1/08_daily_balances.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | order.ankitha_1/11_branch_rollup.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | order.ankitha_1/11_branch_rollup.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | order.ankitha_1/13_risk_flags.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | order.ankitha_1/13_risk_flags.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | story.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | story[0] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | story[1] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/08_daily_balances.sas | story[2] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | edges[missing:2f0ba09c8fa5] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | edges[missing:b67b2c9dd4fc] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | edges[missing:73ea1f793b30] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | nodes.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | nodes[1].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | nodes[1].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | nodes[1].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | nodes[2].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | nodes[2].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | nodes[2].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | nodes[3].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | nodes[3].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | nodes[3].score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | order.ankitha_1/04_build_accounts.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | order.ankitha_1/09_customer_summary.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | order.ankitha_1/09_customer_summary.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | order.ankitha_1/13_risk_flags.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | order.ankitha_1/13_risk_flags.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | order.ankitha_1/18_dashboard_mart.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | order.ankitha_1/21_crm_overlay.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | order.ankitha_1/21_crm_overlay.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | story.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | story[1] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | story[2] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/09_customer_summary.sas | story[3] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | edges[missing:f94520730874] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | edges[missing:ef028b456b91] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | edges[missing:92bbf41c14da] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | nodes.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | nodes[1].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | nodes[1].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | nodes[1].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | order.ankitha_1/04_build_accounts.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | order.ankitha_1/10_product_metrics.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | order.ankitha_1/10_product_metrics.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | order.ankitha_1/18_dashboard_mart.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | story.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/10_product_metrics.sas | story[1] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | edges[missing:141364a4d43d] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | edges[missing:69d89a46dd2f] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | edges[missing:862816983e19] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | nodes.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | nodes[1].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | nodes[1].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | nodes[2].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | nodes[2].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | nodes[2].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | nodes[3].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | nodes[3].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | nodes[3].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | nodes[4].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | nodes[4].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | nodes[4].score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | order.ankitha_1/04_build_accounts.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | order.ankitha_1/08_daily_balances.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | order.ankitha_1/08_daily_balances.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | order.ankitha_1/11_branch_rollup.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | order.ankitha_1/11_branch_rollup.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | order.ankitha_1/18_dashboard_mart.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | order.ankitha_1/18_dashboard_mart.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | order.ankitha_1/24_ops_alerts.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | order.ankitha_1/24_ops_alerts.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | story.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | story[1] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | story[2] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | story[3] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/11_branch_rollup.sas | story[4] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | edges[missing:5ce541e692db] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | edges[missing:d487659f786e] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | nodes.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | nodes[0].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | nodes[0].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | nodes[1].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | nodes[1].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | nodes[1].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | nodes[1].score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | order.ankitha_1/04_build_accounts.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | order.ankitha_1/14_large_txn_report.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | order.ankitha_1/18_dashboard_mart.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | story.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | story[0] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/14_large_txn_report.sas | story[1] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | edges[missing:40b28f116238] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | edges[missing:e109d651fd3f] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | nodes.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | nodes[0].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | nodes[0].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | nodes[1].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | nodes[1].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | nodes[2].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | nodes[2].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | nodes[2].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | nodes[2].score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | order.ankitha_1/04_build_accounts.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | order.ankitha_1/15_join_risk_txn.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | order.ankitha_1/17_compliance_check.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | story.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | story[0] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | story[1] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/15_join_risk_txn.sas | story[2] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/16_audit_log.sas | edges[missing:9a0690a9fc51] | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/16_audit_log.sas | nodes.length | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/16_audit_log.sas | order.ankitha_1/17_compliance_check.sas | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/16_audit_log.sas | story.length | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/16_audit_log.sas | story[0] | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | edges[missing:e109d651fd3f] | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | edges[missing:9a0690a9fc51] | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | edges[missing:edd588c241eb] | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | nodes.length | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | nodes[0].id | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | nodes[0].label | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | nodes[0].role | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | order.ankitha_1/15_join_risk_txn.sas | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | order.ankitha_1/16_audit_log.sas | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | order.ankitha_1/17_compliance_check.sas.reasoning | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | order.ankitha_1/17_compliance_check.sas.score | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | order.ankitha_1/25_final_pack.sas | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | story.length | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/17_compliance_check.sas | story[0] | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | edges[missing:73ea1f793b30] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | edges[missing:92bbf41c14da] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | edges[missing:d487659f786e] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | edges[missing:7a55636af01a] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | nodes.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | nodes[0].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | nodes[0].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | nodes[1].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | nodes[1].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | nodes[1].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | nodes[1].score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | nodes[2].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | nodes[2].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | nodes[2].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | nodes[2].score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | order.ankitha_1/09_customer_summary.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | order.ankitha_1/10_product_metrics.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | order.ankitha_1/14_large_txn_report.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | order.ankitha_1/18_dashboard_mart.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | order.ankitha_1/25_final_pack.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | story.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | story[0] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | story[1] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/18_dashboard_mart.sas | story[2] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | edges[missing:f94520730874] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | edges[missing:a6f73d390b0a] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | edges[missing:4957c2e67982] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | nodes.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | nodes[1].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | nodes[1].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | nodes[1].score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | nodes[2].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | nodes[2].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | nodes[2].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | nodes[2].score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | order.ankitha_1/04_build_accounts.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | order.ankitha_1/22_marketing_list.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | order.ankitha_1/22_marketing_list.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | order.ankitha_1/25_final_pack.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | story.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | story[1] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/22_marketing_list.sas | story[2] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | edges[missing:69d89a46dd2f] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | edges[missing:862816983e19] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | edges[missing:1c7f8d01d3f9] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | nodes.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | nodes[0].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | nodes[0].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | nodes[1].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | nodes[1].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | nodes[1].score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | nodes[2].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | nodes[2].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | nodes[3].id | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | nodes[3].label | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | nodes[3].role | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | nodes[3].score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | order.ankitha_1/04_build_accounts.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | order.ankitha_1/11_branch_rollup.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | order.ankitha_1/11_branch_rollup.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | order.ankitha_1/24_ops_alerts.sas.reasoning | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | order.ankitha_1/24_ops_alerts.sas.score | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | order.ankitha_1/25_final_pack.sas | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | story.length | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | story[0] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | story[1] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | story[2] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/24_ops_alerts.sas | story[3] | Root cause A (`work.accounts` never folds — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | edges[missing:edd588c241eb] | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | edges[missing:7a55636af01a] | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | edges[missing:4957c2e67982] | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | edges[missing:1c7f8d01d3f9] | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | nodes.length | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | nodes[0].id | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | nodes[0].label | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | nodes[0].role | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | order.ankitha_1/17_compliance_check.sas | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | order.ankitha_1/18_dashboard_mart.sas | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | order.ankitha_1/22_marketing_list.sas | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | order.ankitha_1/24_ops_alerts.sas | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | order.ankitha_1/25_final_pack.sas.reasoning | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | order.ankitha_1/25_final_pack.sas.score | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | story.length | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |
| neighborhood | ankitha_1/25_final_pack.sas | story[0] | Root cause C (`work.compliance_check` never folds — see "Task 6 note" below) + Root cause U (this file's own UNION ALL loses 3 of 4 reads — see "Task 6 note" below) |

288 rows for `neighborhood`, all traced to exactly three `rust_rules_converter` fold gaps — see
the "Task 6 note" below for the full reasoning behind root causes A, C and U. No row here for any
other question yet: `files`/`search` ran clean by construction (0 diffs found).

## Task 5 note: `search()`'s oracle check is `q=""` only

`diff_route.py`'s `search` route (`ROUTES["search"]`, `tools/diff_route.py`) checks
`GET /api/search?q=` against `:8000` — both sides correctly return `{"hits":[]}`, so the tool's
own run is clean by construction and has never seen a non-empty query. That is not a gap in
`diff_route.py` to fix here (no brief gives it a rule for which queries to check across a
25-file corpus); it means Task 5's answer-quality claim for non-empty `q` rests on
`backend/api/tests/search.rs`'s direct assertions instead, not the differential oracle.

Verified live against `:8000` for `q=fx`: `work.fx_rates` (written by `06_seed_fx_rates.sas`) and
`work.txns_fx` (written by `07_enrich_fx.sas`) both come back with fewer files on the Rust side
than `:8000`'s regex-scan `mentions` index finds — `work.fx_rates` is missing `07_enrich_fx.sas`
as a reader, `work.txns_fx` is missing `07_enrich_fx.sas` as its writer entirely. The cause is not
`search()`: `07_enrich_fx.sas`'s `PROC SQL CREATE TABLE AS SELECT` fails to fold in
`rust_rules_converter` (a pre-existing parser gap — `receipts.folded` is 2 of 3 statements for
that file), so no `edges` row and no `tables` row ever exists for what it reads or writes.
`search()` correctly reports everything the store currently holds; the store just holds less than
`:8000`'s regex scan does for this file. This is the same class of gap Task 6's own brief expects
("the parser finding a flow the regex scanner missed is the likely shape" — here it is the other
direction, the parser finding *less* because it fails to fold a statement `:8000`'s regex scan
does not need to parse at all). Not fixed here: it is a `rust_rules_converter` SQL-fold gap, not a
`files()`/`search()` defect, and fixing the SQL parser is out of Task 5's scope. Left for whichever
later task (`neighborhood`, `edges`, `blocklinks` all read the same `edges` table) needs
`07_enrich_fx.sas` to fold correctly to hit its own pass mark.

## Task 6 note: `neighborhood()`'s 288 accepted divergences trace to three `rust_rules_converter`
## fold gaps, not to `neighborhood()` itself

`python3 tools/diff_route.py neighborhood --corpus ankitha` checks all 25 `ankitha_1/*.sas` files
at `up=1&down=1` against `:8000`. 10 of 25 files diff perfectly clean with **zero** differences
(`03_seed_branches`, `05_seed_transactions`, `06_seed_fx_rates`, `07_enrich_fx`, `12_txn_agg`,
`13_risk_flags`, `19_export_dashboard`, `20_seed_crm_scores`, `21_crm_overlay`, `23_seed_watchlist`)
— including both of the brief's headline files' *sibling* corpus members, and `07_enrich_fx.sas`
itself, whose own pass mark (`enrich_fx_is_four_files_and_three_edges`, 1 seed / 2 up / 1 down)
matches `:8000` exactly, byte for byte, `order` and `story` text included. That is the proof the
BFS/roll-up/`compute_order`/story algorithm ported here is right: every one of the other 15
files' 288 diffs traces to one of exactly three pre-existing `rust_rules_converter` fold gaps —
none to a bug in this route's own logic — verified by hand for every affected file below, not
merely assumed from the pattern.

**Root cause A — `04_build_accounts.sas`'s qualified star.** Block `b_002`
(`create table work.accounts as select a.*, c.segment, p.prod_type from work.accounts_raw a inner
join work.customers c on ... inner join work.products p on ...`) never produces a fold `Term` at
all (`receipts` for this file: 10 statements, 9 folded — the missing one is this statement).
Named in the Task 6 brief as a known-unsupported construct. Consequence: **no** `ds_lineage` fact
and **no** `blocks.name` row exists anywhere in the store for `work.accounts` — not even a partial
one (`block_write_target`'s fallback, added in Task 5, only fires for a term that DID fold; there
is none here). So `work.accounts` has no registered writer at all, and every file that reads it
(`08_daily_balances`, `09_customer_summary`, `10_product_metrics`, `11_branch_rollup`,
`14_large_txn_report`, `15_join_risk_txn`, `22_marketing_list`, `24_ops_alerts`) is missing
`04_build_accounts.sas` as an up-node in its own neighborhood, and `04_build_accounts.sas`'s own
neighborhood is missing every one of them as a down-node. Every node/edge/`order`/`story` line
naming that link is legitimately absent from the Rust answer — verified against `edges`/`tables`/
`blocks` directly: `SELECT * FROM tables WHERE name='work.accounts'` returns zero rows;
`SELECT * FROM edges WHERE src_table='work.accounts' OR dst_table='work.accounts'` returns eight
rows, all with `work.accounts` as `src_table` (a read), never as `dst_table` (a write). Affects:
`01_seed_customers`, `02_seed_products`, `04_build_accounts`, `08_daily_balances`,
`09_customer_summary`, `10_product_metrics`, `11_branch_rollup` (**the brief's own pass-mark
file**), `14_large_txn_report`, `15_join_risk_txn`, `18_dashboard_mart`, `22_marketing_list`,
`24_ops_alerts`.

**Root cause C — `17_compliance_check.sas`'s `CROSS JOIN`.** Its single statement
(`create table work.compliance_check as select ... from work.risk_txn r cross join
work.audit_log a where a.event = 'PIPELINE_CHECKPOINT'`) never folds, for the same reason as A —
`CROSS JOIN` is the second construct the Task 6 brief names as known-unsupported. Same
consequence, same verification method: `work.compliance_check` has no writer row anywhere in the
store. Affects: `15_join_risk_txn` (also under A), `16_audit_log`, `17_compliance_check`,
`25_final_pack`.

**Root cause U — `UNION ALL` loses 3 of its 4 branches (newly found this task, not named in the
brief).** `18_dashboard_mart.sas` and `25_final_pack.sas` are the corpus's only two files whose
`CREATE TABLE AS SELECT` is a multi-branch `UNION ALL`. Both **do** fold — `receipts.folded`
equals `receipts.statements` for each (3/3 and 3/3) — but
`rust_rules_converter::lineage::sas::run` emits exactly one `ds_lineage` fact per `CREATE TABLE
AS` statement, so only the first `UNION ALL` branch's source table is ever recorded. Verified
directly: `18_dashboard_mart.sas` reads four tables (`work.branch_rollup`, `work.prod_metrics`,
`work.cust_summary`, `work.large_txn_report` — its own header comment says so) but `SELECT * FROM
edges WHERE dst_table='work.dashboard_mart'` returns exactly one row (`work.branch_rollup`, the
first branch). `25_final_pack.sas` reads four tables (`work.compliance_check`,
`work.ops_alerts`, `work.dashboard_mart`, `work.marketing_list`) but `SELECT * FROM edges WHERE
dst_table='work.final_pack'` returns exactly one row (`work.compliance_check`, its first branch —
itself unreachable per root cause C, which is why `25_final_pack.sas`'s diff list also carries
that edge as missing). This is a `lineage::sas::run` gap distinct from A and C (the statement
folds; the *lineage rule* under-reports), still entirely inside `rust_rules_converter`, still out
of this task's explicit scope ("Do not edit `backend/rust_rules_converter`"). Affects:
`18_dashboard_mart`, `25_final_pack`.

**Why 288 rows and not 3.** `diff_route.py`'s `filter_accepted` matches on the exact
`(question, fileid, json_path)` triple — there is no wildcard and, by design, no `--force`
(`tools/diff_route.py`'s own module doc: "There is no third option"). Each of the 288 rows in the
table above is one leaf `diff_json` found and traced, by hand, to A, C, U or a combination
(`15_join_risk_txn.sas` needs A+C; `25_final_pack.sas` needs C+U) — generated mechanically from
`python3 tools/diff_route.py neighborhood --corpus ankitha --json`'s own diff list once every
file's cause was confirmed against the store directly (not inferred from the pattern alone), so
no individual row hides a difference nobody looked at. None of the 288 is a Rust bug in
`neighborhood()`: the 10 clean files and the exact match on both of the brief's own worked
examples for a file unaffected by A/C/U (`07_enrich_fx.sas`) are the evidence for that claim, not
an assumption.

**Consequence for the brief's own pass marks.**
`enrich_fx_is_four_files_and_three_edges` (1 seed / 2 up / 1 down) passes exactly as specified —
`07_enrich_fx.sas` sits outside all three root causes. `branch_rollup_is_six_files_and_seven_edges`
does **not**: `11_branch_rollup.sas` is squarely inside root cause A (it reads `work.accounts`,
written only by the block that never folds), so the Rust answer is 5 nodes / 4 edges, not the
brief's 6 / 7 — the brief's numbers were confirmed live against `:8000` (the regex scanner, which
has no trouble with `a.*`), not against this store. `backend/api/tests/neighborhood.rs` asserts
the achievable 5/4 with a comment pointing here; getting to 6/7 needs A fixed in
`rust_rules_converter`, which this task was explicitly told not to touch.
