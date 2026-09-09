/* ============================================================
   02_seed_products.sas
   Creates : work.products
   Reads   : (none)
   ============================================================ */

data work.products;
  length prod_id $8 prod_name $40 prod_type $12 currency $3;
  infile datalines dsd dlm='|' truncover;
  input prod_id prod_name prod_type currency base_fee;
  datalines;
P01|Checking Basic|DEPOSIT|USD|5
P02|Savings Plus|DEPOSIT|USD|0
P03|SME Line|CREDIT|USD|25
P04|Corp FX|FX|USD|50
P05|Retail Card|CARD|USD|10
;
run;
