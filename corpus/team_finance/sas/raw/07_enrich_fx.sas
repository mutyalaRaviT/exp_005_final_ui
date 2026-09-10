/* ============================================================
   07_enrich_fx.sas
   Creates : work.txns_fx
   Reads   : work.transactions, work.fx_rates
   File deps (table-based):
     - 05_seed_transactions.sas  (work.transactions)
     - 06_seed_fx_rates.sas      (work.fx_rates)
   ============================================================ */

proc sql;
  create table work.txns_fx as
  select
      t.txn_id,
      t.acct_id,
      t.txn_dt,
      t.txn_type,
      t.amount,
      t.ccy,
      coalesce(f.rate_to_usd, 1) as rate_to_usd,
      t.amount * coalesce(f.rate_to_usd, 1) as amount_usd
  from work.transactions t
  left join work.fx_rates f
    on t.ccy = f.ccy
   and t.txn_dt = f.rate_dt;
quit;
