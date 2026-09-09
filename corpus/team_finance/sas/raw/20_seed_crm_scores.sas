/* ============================================================
   20_seed_crm_scores.sas
   Creates : work.crm_scores
   Reads   : (none)
   ============================================================ */

data work.crm_scores;
  length cust_id $8 crm_tier $8;
  infile datalines dsd dlm='|' truncover;
  input cust_id crm_score crm_tier;
  datalines;
C001|0.10|GOLD
C002|0.30|SILVER
C003|0.50|BRONZE
C004|0.90|WATCH
C005|0.05|GOLD
;
run;
