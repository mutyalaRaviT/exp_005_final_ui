/* ============================================================
   13_risk_flags.sas
   Creates : work.risk_flags
   Reads   : work.cust_summary, work.daily_bal
   File deps (table-based):
     - 09_customer_summary.sas  (work.cust_summary)
     - 08_daily_balances.sas    (work.daily_bal)
   ============================================================ */

proc sql;
  create table work.risk_flags as
  select
      c.cust_id,
      c.cust_name,
      c.segment,
      c.risk_score,
      c.total_open_bal,
      sum(d.ledger_bal) as total_ledger_bal,
      case
        when c.risk_score >= 0.75 then 'HIGH'
        when c.risk_score >= 0.40 then 'MED'
        else 'LOW'
      end as risk_band length=8
  from work.cust_summary c
  left join work.daily_bal d
    on c.cust_id = d.cust_id
  group by c.cust_id, c.cust_name, c.segment, c.risk_score, c.total_open_bal;
quit;
