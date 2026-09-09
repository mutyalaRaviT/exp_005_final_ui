/* ============================================================
   22_marketing_list.sas
   Creates : work.marketing_list
   Reads   : work.cust_crm, work.accounts, work.products
   File deps (table-based):
     - 21_crm_overlay.sas      (work.cust_crm)
     - 04_build_accounts.sas   (work.accounts)
     - 02_seed_products.sas    (work.products)
   ============================================================ */

proc sql;
  create table work.marketing_list as
  select
      c.cust_id,
      c.cust_name,
      c.segment,
      c.crm_tier,
      c.blended_score,
      a.prod_id,
      p.prod_name
  from work.cust_crm c
  inner join work.accounts a
    on c.cust_id = a.cust_id
   and a.status = 'OPEN'
  inner join work.products p
    on a.prod_id = p.prod_id
  where c.blended_score < 0.5;
quit;
