/* ============================================================
   05_seed_transactions.sas
   Creates : work.transactions
   Reads   : (none)
   ============================================================ */

data work.transactions;
  length txn_id $12 acct_id $10 txn_type $8 ccy $3;
  infile datalines dsd dlm='|' truncover;
  input txn_id acct_id txn_dt :yymmdd10. txn_type amount ccy;
  format txn_dt yymmdd10.;
  datalines;
T0001|A1001|2026-01-02|DEBIT|150|USD
T0002|A1003|2026-01-02|CREDIT|2000|USD
T0003|A1005|2026-01-03|FX|50000|JPY
T0004|A1004|2026-01-03|DEBIT|1200|USD
T0005|A1002|2026-01-04|DEBIT|50|USD
T0006|A1006|2026-01-04|CREDIT|400|USD
;
run;
