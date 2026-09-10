/* ============================================================
   12_txn_agg.sas
   Creates : work.txn_agg
   Reads   : work.txns_fx
   File deps (table-based):
     - 07_enrich_fx.sas  (work.txns_fx)
   ============================================================ */

proc sql;
  create table work.txn_agg as
  select
      acct_id,
      txn_type,
      count(*) as txn_cnt,
      sum(amount_usd) as amt_usd_sum,
      avg(amount_usd) as amt_usd_avg
  from work.txns_fx
  group by acct_id, txn_type;
quit;
