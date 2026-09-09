/* ============================================================
   16_audit_log.sas
   Creates : work.audit_log
   Reads   : (none)
   ============================================================ */

data work.audit_log;
  length run_id $32 event $40 status $12;
  run_id = 'FD_TABLE_DEPS';
  event  = 'PIPELINE_START';
  status = 'OK';
  event_ts = datetime();
  format event_ts datetime20.;
  output;
  event  = 'PIPELINE_CHECKPOINT';
  status = 'OK';
  event_ts = datetime();
  output;
run;
