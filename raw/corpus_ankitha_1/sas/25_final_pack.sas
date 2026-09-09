/* ============================================================
   25_final_pack.sas
   Creates : work.final_pack
   Reads   : work.compliance_check, work.ops_alerts,
             work.dashboard_mart, work.marketing_list
   File deps (table-based):
     - 17_compliance_check.sas  (work.compliance_check)
     - 24_ops_alerts.sas        (work.ops_alerts)
     - 18_dashboard_mart.sas    (work.dashboard_mart)
     - 22_marketing_list.sas    (work.marketing_list)

   All four parents must finish before 25 can complete.
   ============================================================ */

proc sql;
  create table work.final_pack as
  select
      'COMPLIANCE' as pack_section length=16,
      c.cust_id as key_id,
      c.compliance_flag as flag,
      c.amt_usd_sum as metric_val
  from work.compliance_check c
  union all
  select
      'OPS_ALERT',
      o.cust_id,
      o.risk_band,
      .
  from work.ops_alerts o
  union all
  select
      'DASHBOARD',
      d.key_id,
      d.metric_type,
      d.metric_val
  from work.dashboard_mart d
  union all
  select
      'MARKETING',
      m.cust_id,
      m.crm_tier,
      m.blended_score
  from work.marketing_list m;
quit;
