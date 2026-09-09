/* ============================================================
   19_export_dashboard.sas
   Creates : work.dashboard_export
   Reads   : work.dashboard_mart
   File deps (table-based):
     - 18_dashboard_mart.sas  (work.dashboard_mart)
   ============================================================ */

data work.dashboard_export;
  set work.dashboard_mart;
  export_ts = datetime();
  format export_ts datetime20.;
run;
