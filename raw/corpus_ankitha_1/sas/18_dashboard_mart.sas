/* ============================================================
   18_dashboard_mart.sas
   Creates : work.dashboard_mart
   Reads   : work.branch_rollup, work.prod_metrics,
             work.cust_summary, work.large_txn_report
   File deps (table-based):
     - 11_branch_rollup.sas      (work.branch_rollup)
     - 10_product_metrics.sas    (work.prod_metrics)
     - 09_customer_summary.sas   (work.cust_summary)
     - 14_large_txn_report.sas   (work.large_txn_report)
   ============================================================ */

proc sql;
  create table work.dashboard_mart as
  select
      'BRANCH' as metric_type length=12,
      b.branch_id as key_id,
      b.branch_name as key_name,
      b.total_ledger_bal as metric_val
  from work.branch_rollup b
  union all
  select
      'PRODUCT',
      p.prod_id,
      p.prod_name,
      p.book_bal
  from work.prod_metrics p
  union all
  select
      'CUSTOMER',
      c.cust_id,
      c.cust_name,
      c.total_open_bal
  from work.cust_summary c
  union all
  select
      'LARGETXN',
      l.acct_id,
      l.txn_type,
      l.amt_usd_sum
  from work.large_txn_report l;
quit;
