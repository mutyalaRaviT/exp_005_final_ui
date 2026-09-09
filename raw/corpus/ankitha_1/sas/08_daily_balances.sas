/* ============================================================
   08_daily_balances.sas
   Creates : work.daily_bal
   Reads   : work.accounts
   File deps (table-based):
     - 04_build_accounts.sas  (work.accounts)
   ============================================================ */

proc sql;
  create table work.daily_bal as
  select
      acct_id,
      cust_id,
      prod_id,
      branch_id,
      open_bal,
      open_bal as ledger_bal,
      today() as as_of_dt,
      segment,
      prod_type
  from work.accounts
  where status = 'OPEN';
quit;
