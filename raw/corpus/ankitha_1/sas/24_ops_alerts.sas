/* ============================================================
   24_ops_alerts.sas
   Creates : work.ops_alerts
   Reads   : work.risk_flags, work.branch_rollup, work.accounts, work.watchlist
   File deps (table-based):
     - 13_risk_flags.sas       (work.risk_flags)
     - 11_branch_rollup.sas    (work.branch_rollup)
     - 04_build_accounts.sas   (work.accounts)
     - 23_seed_watchlist.sas   (work.watchlist)
   ============================================================ */

proc sql;
  create table work.ops_alerts as
  select
      r.cust_id,
      r.cust_name,
      r.risk_band,
      b.region,
      w.watch_reason,
      w.watch_dt
  from work.risk_flags r
  left join work.accounts a
    on r.cust_id = a.cust_id
  left join work.branch_rollup b
    on a.branch_id = b.branch_id
  inner join work.watchlist w
    on r.cust_id = w.cust_id
  where r.risk_band in ('HIGH', 'MED');
quit;
