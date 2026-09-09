/* ============================================================
   01_seed_customers.sas
   Creates : work.customers
   Reads   : (none)
   Must run before any file that uses work.customers
   ============================================================ */

data work.customers;
  length cust_id $8 cust_name $40 segment $12 country $3;
  infile datalines dsd dlm='|' truncover;
  input cust_id cust_name segment country open_dt :yymmdd10. risk_score;
  format open_dt yymmdd10.;
  datalines;
C001|Alice Nguyen|RETAIL|USA|2020-01-15|0.20
C002|Bob Smith|RETAIL|USA|2019-06-01|0.45
C003|Carla Diaz|SME|MEX|2021-03-22|0.55
C004|Dan Okada|CORP|JPN|2018-11-09|0.80
C005|Eva Chen|RETAIL|SGP|2022-07-30|0.15
;
run;
