/* ============================================================
   14_large_txn_report.sas
   Creates : work.large_txn_report
   Reads   : work.txn_agg, work.accounts
   File deps (table-based):
     - 12_txn_agg.sas          (work.txn_agg)
     - 04_build_accounts.sas   (work.accounts)
   ============================================================ */

proc sql;
  create table work.large_txn_report as
  select
      t.acct_id,
      a.cust_id,
      a.prod_id,
      a.branch_id,
      t.txn_type,
      t.txn_cnt,
      t.amt_usd_sum
  from work.txn_agg t
  inner join work.accounts a
    on t.acct_id = a.acct_id
  where t.amt_usd_sum >= 1000
  order by t.amt_usd_sum desc;
quit;
