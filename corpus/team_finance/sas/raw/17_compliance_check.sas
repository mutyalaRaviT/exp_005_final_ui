/* ============================================================
   17_compliance_check.sas
   Creates : work.compliance_check
   Reads   : work.risk_txn, work.audit_log
   File deps (table-based):
     - 15_join_risk_txn.sas  (work.risk_txn)
     - 16_audit_log.sas      (work.audit_log)

   Example you asked for:
     15 → work.risk_txn  ─┐
                          ├─→ 17
     16 → work.audit_log ─┘
   Both 15 and 16 must finish before 17 can complete.
   ============================================================ */

proc sql;
  create table work.compliance_check as
  select
      r.cust_id,
      r.risk_band,
      r.amt_usd_sum,
      a.run_id,
      a.event,
      a.status,
      case when r.risk_band = 'HIGH' and r.amt_usd_sum > 1000
           then 'REVIEW'
           else 'PASS'
      end as compliance_flag length=8
  from work.risk_txn r
  cross join work.audit_log a
  where a.event = 'PIPELINE_CHECKPOINT';
quit;
