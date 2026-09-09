/* ============================================================
   09_customer_summary.sas
   Creates : work.cust_summary
   Reads   : work.customers, work.accounts
   File deps (table-based):
     - 01_seed_customers.sas   (work.customers)
     - 04_build_accounts.sas   (work.accounts)
   ============================================================ */

proc sql;
  create table work.cust_summary as
  select
      c.cust_id,
      c.cust_name,
      c.segment,
      c.country,
      c.risk_score,
      count(a.acct_id) as acct_cnt,
      sum(a.open_bal) as total_open_bal
  from work.customers c
  left join work.accounts a
    on c.cust_id = a.cust_id
  group by c.cust_id, c.cust_name, c.segment, c.country, c.risk_score;
quit;
