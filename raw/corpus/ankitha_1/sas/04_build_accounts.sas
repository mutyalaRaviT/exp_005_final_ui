/* ============================================================
   04_build_accounts.sas
   Creates : work.accounts
   Reads   : work.customers, work.products
   File deps (table-based):
     - 01_seed_customers.sas  (work.customers)
     - 02_seed_products.sas    (work.products)
   ============================================================ */

data work.accounts_raw;
  length acct_id $10 cust_id $8 prod_id $8 branch_id $6 status $8;
  infile datalines dsd dlm='|' truncover;
  input acct_id cust_id prod_id branch_id status open_bal;
  datalines;
A1001|C001|P01|B01|OPEN|1200
A1002|C001|P05|B01|OPEN|300
A1003|C002|P02|B02|OPEN|5000
A1004|C003|P03|B03|OPEN|15000
A1005|C004|P04|B04|OPEN|250000
A1006|C005|P01|B05|OPEN|800
A1007|C002|P05|B02|CLOSED|0
;
run;

proc sql;
  create table work.accounts as
  select a.*, c.segment, p.prod_type
  from work.accounts_raw a
  inner join work.customers c on a.cust_id = c.cust_id
  inner join work.products  p on a.prod_id = p.prod_id;
quit;
