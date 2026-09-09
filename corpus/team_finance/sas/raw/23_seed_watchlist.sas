/* ============================================================
   23_seed_watchlist.sas
   Creates : work.watchlist
   Reads   : (none)
   ============================================================ */

data work.watchlist;
  length cust_id $8 watch_reason $40;
  infile datalines dsd dlm='|' truncover;
  input cust_id watch_reason watch_dt :yymmdd10.;
  format watch_dt yymmdd10.;
  datalines;
C004|High risk corp review|2026-01-01
C003|SME monitoring|2026-01-02
;
run;
