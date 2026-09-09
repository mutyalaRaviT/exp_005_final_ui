/* ex4: proc sort with out=, an in-place sort, and proc append */
proc sort data=raw.events out=work.events_sorted;
    by ts id;
run;

proc sort data=work.events_sorted;  /* in-place: read and write same table */
    by id;
run;

proc append base=work.event_history data=work.events_sorted;
run;
