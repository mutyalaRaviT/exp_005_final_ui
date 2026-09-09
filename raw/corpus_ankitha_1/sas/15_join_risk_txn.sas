/* ============================================================
   15_join_risk_txn.sas
   Creates : work.risk_txn
   Reads   : work.risk_flags, work.txn_agg, work.accounts
   File deps (table-based):
     - 13_risk_flags.sas       (work.risk_flags)
     - 12_txn_agg.sas          (work.txn_agg)
     - 04_build_accounts.sas   (work.accounts)
   ============================================================ */

proc sql;
  create table work.risk_txn as
  select
      r.cust_id,
      r.cust_name,
      r.risk_band,
      r.risk_score,
      a.acct_id,
      t.txn_type,
      t.txn_cnt,
      t.amt_usd_sum
  from work.risk_flags r
  inner join work.accounts a
    on r.cust_id = a.cust_id
  left join work.txn_agg t
    on a.acct_id = t.acct_id;
quit;
