/* ex5: proc transpose then a data-step UPDATE feeding a final table */
proc transpose data=work.metrics_long out=work.metrics_wide;
    by id;
    id metric_name;
    var metric_value;
run;

data work.master;
    update work.master work.metrics_wide;
    by id;
run;
