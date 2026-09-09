/* ============================================================
   10_product_metrics.sas
   Creates : work.prod_metrics
   Reads   : work.products, work.accounts
   File deps (table-based):
     - 02_seed_products.sas    (work.products)
     - 04_build_accounts.sas   (work.accounts)
   ============================================================ */

proc sql;
  create table work.prod_metrics as
  select
      p.prod_id,
      p.prod_name,
      p.prod_type,
      p.base_fee,
      count(a.acct_id) as acct_cnt,
      sum(a.open_bal) as book_bal
  from work.products p
  left join work.accounts a
    on p.prod_id = a.prod_id
   and a.status = 'OPEN'
  group by p.prod_id, p.prod_name, p.prod_type, p.base_fee;
quit;
