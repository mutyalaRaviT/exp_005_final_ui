/* ============================================================
   21_crm_overlay.sas
   Creates : work.cust_crm
   Reads   : work.cust_summary, work.crm_scores
   File deps (table-based):
     - 09_customer_summary.sas  (work.cust_summary)
     - 20_seed_crm_scores.sas   (work.crm_scores)
   ============================================================ */

proc sql;
  create table work.cust_crm as
  select
      c.cust_id,
      c.cust_name,
      c.segment,
      c.risk_score as model_risk,
      coalesce(m.crm_score, 0) as crm_score,
      coalesce(m.crm_tier, 'UNK') as crm_tier length=8,
      (c.risk_score * 0.6) + (coalesce(m.crm_score, 0) * 0.4) as blended_score
  from work.cust_summary c
  left join work.crm_scores m
    on c.cust_id = m.cust_id;
quit;
