/* ============================================================
   06_seed_fx_rates.sas
   Creates : work.fx_rates
   Reads   : (none)
   ============================================================ */

data work.fx_rates;
  length ccy $3;
  infile datalines dsd dlm='|' truncover;
  input ccy rate_dt :yymmdd10. rate_to_usd;
  format rate_dt yymmdd10.;
  datalines;
USD|2026-01-02|1
USD|2026-01-03|1
USD|2026-01-04|1
JPY|2026-01-03|0.0067
;
run;
