/* ============================================================
   11_branch_rollup.sas
   Creates : work.branch_rollup
   Reads   : work.branches, work.accounts, work.daily_bal
   File deps (table-based):
     - 03_seed_branches.sas    (work.branches)
     - 04_build_accounts.sas   (work.accounts)
     - 08_daily_balances.sas   (work.daily_bal)
   ============================================================ */

proc sql;
  create table work.branch_rollup as
  select
      b.branch_id,
      b.branch_name,
      b.region,
      count(distinct a.acct_id) as acct_cnt,
      sum(d.ledger_bal) as total_ledger_bal
  from work.branches b
  left join work.accounts a
    on b.branch_id = a.branch_id
  left join work.daily_bal d
    on a.acct_id = d.acct_id
  group by b.branch_id, b.branch_name, b.region;
quit;
