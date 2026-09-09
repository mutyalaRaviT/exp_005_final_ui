/* ex3: data _null_ report step (reads, writes nothing) and a view with
   slash options; the string contains a fake semicolon and a fake run */
data _null_;
    set work.summary end=done;
    put "checking; run; not real statements" id= total=;
    if done then put "rows: " _n_;
run;

data work.v_active / view=work.v_active;
    set work.customers(where=(active=1));
run;
